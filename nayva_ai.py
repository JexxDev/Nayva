import time
import os
import torch
import pygame
import ctypes
import sys
from ultralytics import YOLO
from threading import Thread
from pynput import keyboard, mouse
import win32api
import win32con
import glob
from collections import deque

# ================= CONFIGURATION =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Recherche plus large du modèle best.pt (runs/detect/trainX/weights/best.pt, etc.)
model_files = glob.glob(os.path.join(BASE_DIR, "**", "best.pt"), recursive=True)

if not model_files:
    print("Répertoires trouvés dans le dossier de nayva_ai.py :")
    print(os.listdir(BASE_DIR))
    print("\nEt dans les sous-dossiers :")
    for root, dirs, files in os.walk(BASE_DIR):
        if "best.pt" in files:
            print("  →", os.path.join(root, "best.pt"))
    raise FileNotFoundError("best.pt introuvable dans le dossier nayva_ai.py et ses sous-dossiers")

MODEL_PATH = model_files[0]
print(f"Modèle chargé : {MODEL_PATH}")

CONF_MIN = 0.20          # un peu plus bas que 0.22
CONF_MIN_AIM = 0.38      # ↓ pour lock plus facilement

SCREEN_WIDTH = 3440
SCREEN_HEIGHT = 1440

SHOW_BOXES = False       # désactivé par défaut (invisible)
SHOW_PREDICTION_DOT = True

YOLO_SIZE = 640
MAX_DET = 100

CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
CAPTURE_LEFT = (SCREEN_WIDTH - CAPTURE_WIDTH) // 2
CAPTURE_TOP = (SCREEN_HEIGHT - CAPTURE_HEIGHT) // 2
CAPTURE_REGION = (CAPTURE_LEFT, CAPTURE_TOP, CAPTURE_LEFT + CAPTURE_WIDTH, CAPTURE_TOP + CAPTURE_HEIGHT)

CENTER_X = SCREEN_WIDTH // 2
CENTER_Y = SCREEN_HEIGHT // 2
CENTER_TOLERANCE_X = 110     # un peu plus large
CENTER_TOLERANCE_Y = 150     # idem

TARGET_CLASSES = ["Character", "Sniper"]

AIM_ASSIST_ENABLED = True
AIM_DEADZONE = 10            # plus réactif
SMOOTHING = 0.38             # ↑ plus rapide mais toujours contrôlable
MAX_SPEED = 20               # ↑ pour rattraper vite

SLOWDOWN_BASE = 0.18
SLOWDOWN_DISTANCE_SCALE = 650

HEAD_OFFSET_RATIO = 0.26     # un peu plus haut

SWITCH_THRESHOLD = 220       # ↑ encore plus dur à switcher
LOCK_PERSISTENCE = 35        # ↑ lock beaucoup plus collant

CLICK_COOLDOWN = 0.014

POSITION_HISTORY_SIZE = 5
position_history = {}

# ===================== FONCTIONS =====================
def distance_to_center(tx, ty):
    return ((tx - CENTER_X)**2 + (ty - CENTER_Y)**2)**0.5

def predict_position(track_id, current_x, current_y, current_time):
    if track_id not in position_history:
        position_history[track_id] = deque(maxlen=POSITION_HISTORY_SIZE)
    
    position_history[track_id].append((current_x, current_y, current_time))
    
    if len(position_history[track_id]) < 2:
        return current_x, current_y
    
    history = list(position_history[track_id])
    vx_sum = vy_sum = count = 0
    
    for i in range(1, len(history)):
        dt = history[i][2] - history[i-1][2]
        if dt > 0:
            vx_sum += (history[i][0] - history[i-1][0]) / dt
            vy_sum += (history[i][1] - history[i-1][1]) / dt
            count += 1
    
    if count == 0:
        return current_x, current_y
    
    vx_avg = vx_sum / count
    vy_avg = vy_sum / count
    
    dist = distance_to_center(current_x, current_y)
    lead_time = 0.065 + (dist / 1800) * 0.12   # ↑ un peu plus agressif
    
    return current_x + vx_avg * lead_time, current_y + vy_avg * lead_time

def is_in_center(cx, cy):
    return (abs(cx - CENTER_X) <= CENTER_TOLERANCE_X and
            abs(cy - CENTER_Y) <= CENTER_TOLERANCE_Y)

def windows_click():
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.007)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def roblox_move_mouse(dx, dy):
    dx = round(dx)
    dy = round(dy)
    if abs(dx) < 0.5: dx = 0
    if abs(dy) < 0.5: dy = 0
    if dx == 0 and dy == 0: return
    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)

def gentle_aim_move(target_x, target_y):
    global last_aim_x, last_aim_y
    
    dx = target_x - CENTER_X
    dy = target_y - CENTER_Y
    dist = (dx**2 + dy**2)**0.5
    
    if dist < AIM_DEADZONE:
        return 0, 0

    slowdown = SLOWDOWN_BASE + (dist / SLOWDOWN_DISTANCE_SCALE) * (1.0 - SLOWDOWN_BASE)
    slowdown = min(1.0, max(SLOWDOWN_BASE, slowdown))

    move_x = dx * SMOOTHING * slowdown
    move_y = dy * SMOOTHING * slowdown

    move_x = max(-MAX_SPEED, min(MAX_SPEED, move_x))
    move_y = max(-MAX_SPEED, min(MAX_SPEED, move_y))

    roblox_move_mouse(move_x, move_y)
    last_aim_x, last_aim_y = target_x, target_y
    return move_x, move_y

# ================= PYGAME OVERLAY (optionnel) =================
def overlay_loop():
    pass  # overlay invisible si tu veux

# ================= DÉTECTION =================
def detect_loop():
    global locked_track_id, frames_without_lock, predicted_points, detections_for_overlay, stats_text, middle_mouse_pressed

    model = YOLO(MODEL_PATH)
    camera = bettercam.create(region=CAPTURE_REGION, output_color="BGR")
    camera.start(target_fps=144)

    last_click_time = 0
    prev_time = time.time()

    locked_track_id = None
    frames_without_lock = 0
    predicted_points = []
    detections_for_overlay = []
    middle_mouse_pressed = False

    while True:
        start_time = time.time()
        frame = camera.get_latest_frame()
        if frame is None:
            continue

        results = model.track(
            frame,
            conf=CONF_MIN,
            imgsz=YOLO_SIZE,
            max_det=MAX_DET,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False
        )[0]

        detections_for_overlay = []
        predicted_points = []
        valid_targets = []
        current_time = time.time()

        if results.boxes.id is not None:
            boxes = results.boxes.xyxy.cpu().numpy()
            confs = results.boxes.conf.cpu().numpy()
            classes = results.boxes.cls.cpu().numpy()
            track_ids = results.boxes.id.int().cpu().numpy()

            for i in range(len(boxes)):
                x1, y1, x2, y2 = map(int, boxes[i])
                x1 += CAPTURE_LEFT
                x2 += CAPTURE_LEFT
                y1 += CAPTURE_TOP
                y2 += CAPTURE_TOP

                cls_idx = int(classes[i])
                cls_name = model.names[cls_idx]
                tid = int(track_ids[i])

                box_height = y2 - y1
                head_offset = int(box_height * HEAD_OFFSET_RATIO)
                
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2 - head_offset

                pred_x, pred_y = predict_position(tid, cx, cy, current_time)
                predicted_points.append((pred_x, pred_y, tid))

                if confs[i] >= CONF_MIN_AIM and cls_name in TARGET_CLASSES:
                    dist = distance_to_center(pred_x, pred_y)
                    valid_targets.append((pred_x, pred_y, tid, confs[i], dist))

        lock_found = False
        
        if locked_track_id is not None:
            for px, py, tid, conf, dist in valid_targets:
                if tid == locked_track_id:
                    lock_found = True
                    frames_without_lock = 0
                    break
            
            if not lock_found:
                frames_without_lock += 1
                if frames_without_lock > LOCK_PERSISTENCE:
                    locked_track_id = None
                    frames_without_lock = 0

        if valid_targets:
            valid_targets.sort(key=lambda t: t[4])
            best_px, best_py, best_tid, best_conf, best_dist = valid_targets[0]

            if locked_track_id is None:
                locked_track_id = best_tid
                frames_without_lock = 0

            elif lock_found:
                current_dist = next((d for _, _, tid, _, d in valid_targets if tid == locked_track_id), None)
                if current_dist is not None and best_dist < current_dist - SWITCH_THRESHOLD:
                    locked_track_id = best_tid
                    frames_without_lock = 0

        target_x = target_y = None
        
        if AIM_ASSIST_ENABLED and locked_track_id is not None and middle_mouse_pressed:
            for px, py, tid in predicted_points:
                if tid == locked_track_id:
                    target_x, target_y = px, py
                    gentle_aim_move(target_x, target_y)
                    break

        curr_t = time.time()
        if curr_t - last_click_time >= CLICK_COOLDOWN and locked_track_id is not None and middle_mouse_pressed:
            if target_x is not None and target_y is not None and is_in_center(target_x, target_y):
                windows_click()
                last_click_time = curr_t

        end_time = time.time()
        latency = (end_time - start_time) * 1000
        fps = 1 / (end_time - prev_time) if end_time - prev_time > 0 else 0
        prev_time = end_time

def on_press(key):
    global locked_track_id, frames_without_lock, position_history
    if key == keyboard.Key.esc:
        pygame.quit()
        sys.exit(0)
    if key == keyboard.KeyCode.from_char('r'):
        locked_track_id = None
        frames_without_lock = 0
        position_history.clear()

def on_click(x, y, button, pressed):
    global middle_mouse_pressed
    if button == mouse.Button.middle:
        middle_mouse_pressed = pressed

# ================= LANCEMENT =================
if __name__ == "__main__":
    Thread(target=detect_loop, daemon=True).start()
    # Thread(target=overlay_loop, daemon=True).start()   # ← commente si tu veux full invisible

    keyboard.Listener(on_press=on_press).start()
    mouse.Listener(on_click=on_click).start()

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit(0)
