import time
import os
import torch
import pydirectinput
import tkinter as tk
from ultralytics import YOLO
from threading import Thread
from pynput import keyboard
import ctypes
import sys
import win32api
import win32con
import glob

# Dossier où est nayva_ai.py (et où le zip modèle est extrait)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Recherche automatique de best.pt (très fiable)
model_files = glob.glob(os.path.join(BASE_DIR, "**", "best.pt"), recursive=True)

if model_files:
    MODEL_PATH = model_files[0]  # Prend le premier trouvé (normalement y en a qu'un)
    print(f"Modèle trouvé automatiquement : {MODEL_PATH}")
else:
    print("ERREUR : Aucun best.pt trouvé !")
    print("Dossier actuel :", BASE_DIR)
    print("Fichiers présents :", os.listdir(BASE_DIR))
    # Debug plus profond si besoin
    print("Recherche complète :", glob.glob(os.path.join(BASE_DIR, "**/*"), recursive=True))
    raise FileNotFoundError("best.pt introuvable dans l'extraction")

model = YOLO(MODEL_PATH)

# ===================== CONFIG GÉNÉRALE =====================
CONF_MIN = 0.6                
CONF_MIN_AIM = 0.6     
SCREEN_WIDTH = 3440
SCREEN_HEIGHT = 1440

YOLO_SIZE = 1024
MAX_DET = 100

CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
CAPTURE_LEFT = (SCREEN_WIDTH - CAPTURE_WIDTH) // 2
CAPTURE_TOP = (SCREEN_HEIGHT - CAPTURE_HEIGHT) // 2
CAPTURE_REGION = (CAPTURE_LEFT, CAPTURE_TOP, CAPTURE_LEFT + CAPTURE_WIDTH, CAPTURE_TOP + CAPTURE_HEIGHT)

# CENTRE RÉEL de l'écran (pas de la capture!)
CENTER_X = SCREEN_WIDTH // 2
CENTER_Y = SCREEN_HEIGHT // 2
CENTER_TOLERANCE = 40
CLICK_COOLDOWN = 0.01

# === AIM ASSIST ADAPTATIF ===
AIM_ASSIST_ENABLED = True
AIM_DEADZONE = 15                   # Deadzone réduite
BASE_SPEED = 0.4                    # Vitesse augmentée
MIN_SPEED = 1                       # Vitesse minimum
MAX_SPEED = 10                      # Vitesse maximum augmentée
SMOOTHING = 0.25                    # Plus réactif
MIN_MOVE_THRESHOLD = 0.5            # Accepte mouvements plus petits
OSCILLATION_COOLDOWN = 0.15         # Cooldown réduit
FORCE_MOVE_IF_FAR = True            # Force mouvement si distance > 50px

# === VERROUILLAGE DE CIBLE ===
TARGET_LOCK_ENABLED = True          # Active le verrouillage
LOCK_SWITCH_THRESHOLD = 150         # Distance min pour changer de cible (pixels)
LOCK_DETECTION_COUNT = 3            # Nombre de frames avant de verrouiller
LOCK_LOST_TIMEOUT = 0.5             # Temps avant de perdre le lock (secondes)

CLASS_COLORS = {0: "red", 1: "green"}

# ===================== IMPORT BETTERCAM =====================
try:
    import bettercam
except ImportError:
    print("❌ bettercam n'est pas installé. Installe-le avec : pip install bettercam")
    sys.exit(1)

# ===================== VERROUILLAGE DE CIBLE =====================
class TargetLock:
    def __init__(self):
        self.locked_target = None       # Position de la cible verrouillée
        self.locked_box = None          # Box complète de la cible
        self.lock_frames = 0            # Compteur de frames
        self.last_seen = 0              # Timestamp dernière détection
        self.is_locked = False          # État du verrouillage
    
    def update(self, all_targets):
        """
        Met à jour le verrouillage de cible
        Reste sur la même cible sauf si elle disparaît ou qu'une autre est BEAUCOUP plus proche
        """
        current_time = time.time()
        
        if not all_targets:
            # Aucune cible détectée
            if current_time - self.last_seen > LOCK_LOST_TIMEOUT:
                self.reset()
                return None
            # Garde la dernière cible pendant TIMEOUT
            return self.locked_target
        
        # Si pas de lock actuel, trouve la plus proche
        if not self.is_locked or self.locked_target is None:
            best_target = min(all_targets, key=lambda d: distance_to_center(*get_center_point(d)))
            target_pos = get_center_point(best_target)
            
            self.lock_frames += 1
            
            if self.lock_frames >= LOCK_DETECTION_COUNT:
                # VERROUILLAGE ACTIVÉ
                self.locked_target = target_pos
                self.locked_box = best_target
                self.is_locked = True
                self.last_seen = current_time
                print(f"🔒 CIBLE VERROUILLÉE à ({target_pos[0]:.0f}, {target_pos[1]:.0f})")
                return best_target
            else:
                print(f"🔍 Acquisition cible... {self.lock_frames}/{LOCK_DETECTION_COUNT}")
                return best_target
        
        # Lock actif : cherche la cible la plus proche de la position verrouillée
        locked_x, locked_y = self.locked_target
        
        # Trouve la détection la plus proche de la position verrouillée
        def distance_to_locked(det):
            cx, cy = get_center_point(det)
            return ((cx - locked_x)**2 + (cy - locked_y)**2)**0.5
        
        closest_to_lock = min(all_targets, key=distance_to_locked)
        closest_lock_dist = distance_to_locked(closest_to_lock)
        
        # Trouve aussi la plus proche du centre écran (pour comparer)
        closest_to_center = min(all_targets, key=lambda d: distance_to_center(*get_center_point(d)))
        closest_center_dist = distance_to_center(*get_center_point(closest_to_center))
        
        # Switch de cible seulement si :
        # 1. La cible verrouillée a disparu (dist > seuil)
        # 2. OU une autre cible est BEAUCOUP plus proche du centre
        should_switch = False
        
        if closest_lock_dist > LOCK_SWITCH_THRESHOLD:
            # Cible verrouillée trop loin, probablement disparue
            should_switch = True
            print(f"❌ Cible perdue (dist={closest_lock_dist:.0f}px)")
        elif closest_to_center != closest_to_lock:
            # Calcule si l'autre cible est significativement plus proche
            center_advantage = closest_lock_dist - closest_center_dist
            if center_advantage > LOCK_SWITCH_THRESHOLD:
                should_switch = True
                print(f"🔄 Switch: autre cible {center_advantage:.0f}px plus proche")
        
        if should_switch:
            # Réinitialise et recommence l'acquisition
            self.reset()
            return self.update(all_targets)
        
        # Garde la cible verrouillée
        new_pos = get_center_point(closest_to_lock)
        self.locked_target = new_pos
        self.locked_box = closest_to_lock
        self.last_seen = current_time
        
        return closest_to_lock
    
    def reset(self):
        """Réinitialise le verrouillage"""
        if self.is_locked:
            print(f"🔓 Verrouillage perdu")
        self.locked_target = None
        self.locked_box = None
        self.lock_frames = 0
        self.is_locked = False
    
    def get_lock_info(self):
        """Info pour l'overlay"""
        return {
            'is_locked': self.is_locked,
            'position': self.locked_target,
            'frames': self.lock_frames
        }

# Instance globale
target_lock = TargetLock()

# ===================== FONCTIONS UTILITAIRES =====================
def windows_click():
    """Click qui marche avec Roblox"""
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.01)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def roblox_move_mouse(dx, dy):
    """
    Mouvement souris qui FONCTIONNE avec Roblox
    Utilise win32api au lieu de pydirectinput
    """
    if dx == 0 and dy == 0:
        return
    
    # win32api utilise des coordonnées relatives directement
    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
    print(f"🖱️ WIN32 moveRel({int(dx)}, {int(dy)})")

def is_in_center(x1, y1, x2, y2):
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    return abs(cx - CENTER_X) <= CENTER_TOLERANCE and abs(cy - CENTER_Y) <= CENTER_TOLERANCE

def get_head_point(det):
    """Point sur la tête (20% du haut)"""
    x1, y1, x2, y2 = det[:4]
    return (x1 + x2) / 2, y1 + (y2 - y1) * 0.20

def get_center_point(det):
    """Centre exact de la box"""
    x1, y1, x2, y2 = det[:4]
    return (x1 + x2) / 2, (y1 + y2) / 2

def get_box_size(det):
    """Retourne largeur et hauteur de la box"""
    x1, y1, x2, y2 = det[:4]
    width = x2 - x1
    height = y2 - y1
    return width, height

def calculate_adaptive_speed(box_width, box_height):
    """
    Calcule la vitesse en fonction de la taille de la box
    Petite box (100x100) = 1px/frame
    Grande box (600x600) = 6px/frame
    """
    # Taille moyenne de la box
    avg_size = (box_width + box_height) / 2
    
    # Vitesse proportionnelle
    speed = int(avg_size * BASE_SPEED)
    
    # Limite entre MIN et MAX
    speed = max(MIN_SPEED, min(MAX_SPEED, speed))
    
    return speed

def distance_to_center(tx, ty):
    return ((tx - CENTER_X)**2 + (ty - CENTER_Y)**2)**0.5

# MOUVEMENT ADAPTATIF FORCÉ
last_oscillation_time = 0

def gentle_aim_move(target_x, target_y, box_width, box_height, last_move_x=0, last_move_y=0):
    """
    Déplace vers le CENTRE de la box avec vitesse adaptative
    FORCE le mouvement si distance > 50px
    """
    global last_oscillation_time
    
    # Distance brute
    dx = target_x - CENTER_X
    dy = target_y - CENTER_Y
    
    distance = (dx**2 + dy**2)**0.5
    
    # Vitesse adaptative basée sur taille de box
    adaptive_speed = calculate_adaptive_speed(box_width, box_height)
    
    # DEBUG SIMPLIFIÉ (pas à chaque frame si pas de mouvement)
    should_print_debug = distance > AIM_DEADZONE
    
    if should_print_debug:
        print(f"\n{'='*60}")
        print(f"📦 BOX: {box_width:.0f}x{box_height:.0f}px → Speed:{adaptive_speed}px/f")
        print(f"📏 Distance:{distance:.0f}px | dX:{dx:+.0f} dY:{dy:+.0f}")
    
    # DEADZONE : si déjà au centre, STOP
    if distance < AIM_DEADZONE:
        if should_print_debug:
            print(f"✅ CENTRÉ (deadzone={AIM_DEADZONE}px)")
            print(f"{'='*60}\n")
        return 0, 0
    
    # Pause après oscillation
    if time.time() - last_oscillation_time < OSCILLATION_COOLDOWN:
        print(f"⏸️ Cooldown oscillation...")
        return last_move_x, last_move_y
    
    # Calcul du mouvement
    if distance > 0:
        # Direction normalisée
        norm_dx = dx / distance
        norm_dy = dy / distance
        
        # Force adaptative
        move_strength = min(distance * SMOOTHING, adaptive_speed)
        
        # Mouvement calculé
        move_x = norm_dx * move_strength
        move_y = norm_dy * move_strength
        
        # FORCE MOVE si loin (évite le "point vert mais pas de mouvement")
        if FORCE_MOVE_IF_FAR and distance > 50:
            # Si arrondi donne 0, force au moins 1px dans la bonne direction
            if abs(move_x) < 1 and abs(dx) > 5:
                move_x = 1 if dx > 0 else -1
            if abs(move_y) < 1 and abs(dy) > 5:
                move_y = 1 if dy > 0 else -1
            print(f"💪 FORCE MOVE activé (dist={distance:.0f}px)")
        
        # Arrondi
        if abs(move_x) >= MIN_MOVE_THRESHOLD or abs(move_y) >= MIN_MOVE_THRESHOLD:
            move_x_final = round(move_x)
            move_y_final = round(move_y)
            
            # Limite par vitesse adaptative
            move_x_final = max(-adaptive_speed, min(adaptive_speed, move_x_final))
            move_y_final = max(-adaptive_speed, min(adaptive_speed, move_y_final))
            
            # ANTI-OSCILLATION simplifié
            direction_flip = False
            
            if last_move_y != 0 and move_y_final != 0:
                if (last_move_y > 0) != (move_y_final > 0):
                    direction_flip = True
                    print(f"⚠️ FLIP Y: {last_move_y:+d}→{move_y_final:+d}")
            
            if last_move_x != 0 and move_x_final != 0:
                if (last_move_x > 0) != (move_x_final > 0):
                    direction_flip = True
                    print(f"⚠️ FLIP X: {last_move_x:+d}→{move_x_final:+d}")
            
            if direction_flip:
                print(f"🛑 Pause oscillation")
                last_oscillation_time = time.time()
                return 0, 0
            
            if move_x_final != 0 or move_y_final != 0:
                print(f"🎯 Move X:{move_x_final:+d} Y:{move_y_final:+d}")
                roblox_move_mouse(move_x_final, move_y_final)
                if should_print_debug:
                    print(f"{'='*60}\n")
                return move_x_final, move_y_final
        else:
            # Mouvement calculé trop petit
            print(f"❌ Mouvement trop petit: X={move_x:.2f} Y={move_y:.2f} (arrondi→0)")
            
            # FORCE AU MOINS 1 pixel si vraiment loin
            if distance > 100:
                force_x = 1 if dx > 0 else -1 if dx < 0 else 0
                force_y = 1 if dy > 0 else -1 if dy < 0 else 0
                if force_x != 0 or force_y != 0:
                    print(f"💪 FORCE 1px: X:{force_x:+d} Y:{force_y:+d}")
                    roblox_move_mouse(force_x, force_y)
                    return force_x, force_y
    
    if should_print_debug:
        print(f"{'='*60}\n")
    return 0, 0

# ===================== OVERLAY TKINTER =====================
class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("YOLO Overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}+0+0")

        transparent_color = "magenta"
        self.canvas = tk.Canvas(self.root, width=SCREEN_WIDTH, height=SCREEN_HEIGHT,
                                bg=transparent_color, highlightthickness=0)
        self.canvas.pack()
        self.root.wm_attributes("-transparentcolor", transparent_color)
        self.root.wm_attributes("-disabled", True)

        if sys.platform == "win32":
            self.root.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            extended_style = 0x80000 | 0x20 | 0x08000000
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, extended_style)

        self.detections = []
        self.class_names = {}
        self.canvas_objects = []
        self.aim_targets = []

    def schedule_update(self, detections, class_names, aim_targets=[]):
        self.detections = detections
        self.class_names = class_names
        self.aim_targets = aim_targets
        try:
            self.root.after_idle(self._do_update)
        except:
            pass

    def _do_update(self):
        for obj_id in self.canvas_objects:
            try:
                self.canvas.delete(obj_id)
            except:
                pass
        self.canvas_objects.clear()

        # Petit point rouge au centre (discret)
        center_dot = self.canvas.create_oval(CENTER_X-3, CENTER_Y-3, CENTER_X+3, CENTER_Y+3, fill="red", outline="red")
        self.canvas_objects.append(center_dot)

        if not self.detections:
            return

        for det in self.detections:
            x1, y1, x2, y2, conf, cls = det
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            cls = int(cls)

            in_center = is_in_center(x1, y1, x2, y2)
            color = "yellow" if in_center else CLASS_COLORS.get(cls, "white")
            width = 5 if in_center else 3

            box_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=width)
            self.canvas_objects.append(box_id)

            label = f"{self.class_names.get(cls, f'C{cls}')} {conf:.2f}"
            if in_center:
                label += " 🎯"

            bg_id = self.canvas.create_rectangle(x1, y1 - 20, x1 + len(label) * 8, y1, fill="black", outline="")
            text_id = self.canvas.create_text(x1 + 3, y1 - 10, text=label, fill=color, anchor="w", font=("Arial", 10, "bold"))
            self.canvas_objects.extend([bg_id, text_id])

        # Cible actuelle (gros point vert)
        for target in self.aim_targets:
            tx, ty = int(target[0]), int(target[1])
            
            # Distance au centre
            dist = ((tx - CENTER_X)**2 + (ty - CENTER_Y)**2)**0.5
            in_deadzone = dist < AIM_DEADZONE
            
            # Couleur selon état de lock
            lock_info = target_lock.get_lock_info()
            if lock_info['is_locked']:
                target_color = "lime"      # Vert brillant = locked
            elif lock_info['frames'] > 0:
                target_color = "yellow"    # Jaune = acquisition
            else:
                target_color = "orange"    # Orange = pas de lock
            
            circle_id = self.canvas.create_oval(tx-12, ty-12, tx+12, ty+12, fill=target_color, outline=target_color, width=4)
            cross1_id = self.canvas.create_line(tx-8, ty, tx+8, ty, fill=target_color, width=4)
            cross2_id = self.canvas.create_line(tx, ty-8, tx, ty+8, fill=target_color, width=4)
            self.canvas_objects.extend([circle_id, cross1_id, cross2_id])
            
            # Affiche distance et état lock
            if lock_info['is_locked']:
                status = "🔒 LOCKED"
            elif lock_info['frames'] > 0:
                status = f"🔍 {lock_info['frames']}/{LOCK_DETECTION_COUNT}"
            else:
                status = f"{dist:.0f}px"
            
            dist_text = self.canvas.create_text(tx, ty + 25, text=status, 
                                               fill="white", font=("Arial", 11, "bold"))
            self.canvas_objects.append(dist_text)

    def run(self):
        self.root.mainloop()

    def close(self):
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass

# ===================== BOUCLE DE DÉTECTION =====================
overlay_instance = None
last_move_x = 0
last_move_y = 0

def detect_loop():
    global overlay_instance, last_move_x, last_move_y

    print("🚀 AIMBOT AVEC VERROUILLAGE DE CIBLE")
    print("🟢 Point VERT BRILLANT = cible verrouillée")
    print("🟡 Point JAUNE = acquisition (3 frames)")
    print("🟠 Point ORANGE = détection simple")
    print("🔒 Reste sur la même cible (évite les switch)")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = YOLO(MODEL_PATH)
    class_names = model.names

    camera = bettercam.create(region=CAPTURE_REGION, output_color="BGR")
    camera.start(target_fps=144)

    while overlay_instance is None:
        time.sleep(0.1)

    print("✅ Démarré")

    last_click_time = 0
    last_detections = []

    while True:
        frame = camera.get_latest_frame()
        if frame is None:
            time.sleep(0.001)
            continue

        results = model(frame, conf=CONF_MIN, imgsz=YOLO_SIZE,
                        max_det=MAX_DET, device=device, verbose=False)[0]

        detections = []
        valid_targets = []
        aim_target_points = []

        if results.boxes is not None and len(results.boxes) > 0:
            boxes = results.boxes.xyxy.cpu().numpy()
            confs = results.boxes.conf.cpu().numpy()
            classes = results.boxes.cls.cpu().numpy()

            for i in range(len(boxes)):
                x1, y1, x2, y2 = boxes[i]
                x1 += CAPTURE_LEFT
                y1 += CAPTURE_TOP
                x2 += CAPTURE_LEFT
                y2 += CAPTURE_TOP

                conf = confs[i]
                cls = int(classes[i])

                detections.append([x1, y1, x2, y2, conf, cls])

                if conf >= CONF_MIN_AIM:
                    valid_targets.append([x1, y1, x2, y2, conf, cls])

            last_detections = detections

            # === AIM ASSIST AVEC VERROUILLAGE ===
            if AIM_ASSIST_ENABLED and valid_targets:
                
                # SYSTÈME DE VERROUILLAGE
                if TARGET_LOCK_ENABLED:
                    best_det = target_lock.update(valid_targets)
                else:
                    # Mode classique : toujours la plus proche
                    best_det = min(valid_targets, key=lambda d: distance_to_center(*get_center_point(d)))
                
                if best_det is not None:
                    # VISE LE CENTRE de la box
                    target_x, target_y = get_center_point(best_det)
                    box_width, box_height = get_box_size(best_det)
                    
                    aim_target_points.append([target_x, target_y])

                    # Mouvement adaptatif basé sur taille box
                    last_move_x, last_move_y = gentle_aim_move(
                        target_x, target_y, box_width, box_height, last_move_x, last_move_y
                    )

            # Auto-click si cible au centre
            current_time = time.time()
            if current_time - last_click_time >= CLICK_COOLDOWN:
                for det in detections:
                    if is_in_center(*det[:4]):
                        windows_click()
                        last_click_time = current_time
                        print("💥 CLICK WIN32!")
                        break

        else:
            detections = last_detections

        overlay_instance.schedule_update(detections, class_names, aim_target_points)
        time.sleep(0.001)

    camera.stop()

# ===================== QUITTER =====================
def on_press(key):
    global overlay_instance
    if key == keyboard.Key.esc:
        print("\n🛑 Arrêt")
        if overlay_instance:
            overlay_instance.close()
        os._exit(0)

# ===================== MAIN =====================
if __name__ == "__main__":
    # Vérifie que win32api est installé
    try:
        import win32api
        import win32con
    except ImportError:
        print("❌ pywin32 n'est pas installé!")
        print("📦 Installe-le avec: pip install pywin32")
        sys.exit(1)

    pydirectinput.PAUSE = False
    pydirectinput.FAILSAFE = True

    print("=" * 60)
    print("🎮 AIMBOT ROBLOX - VERROUILLAGE DE CIBLE")
    print("=" * 60)
    print("")
    print("✅ VERROUILLAGE INTELLIGENT:")
    print("   🔍 Détecte 3 frames avant de lock")
    print("   🔒 Reste sur la même personne")
    print("   🔄 Switch seulement si:")
    print("      - Cible perdue (>150px)")
    print("      - Autre cible 150px+ plus proche")
    print("")
    print("🎨 INDICATEURS VISUELS:")
    print("   🟢 VERT BRILLANT = Cible verrouillée")
    print("   🟡 JAUNE = Acquisition (1/3, 2/3...)")
    print("   🟠 ORANGE = Détection simple")
    print("   🔴 Point rouge = Centre écran")
    print("")
    print("📊 Console affiche:")
    print("   🔒 CIBLE VERROUILLÉE")
    print("   🔍 Acquisition cible... 2/3")
    print("   ❌ Cible perdue")
    print("   🔄 Switch: autre cible XXXpx plus proche")
    print("")
    print("🔧 RÉGLAGES (en haut du fichier):")
    print("   BASE_SPEED = 0.05")
    print("   LOCK_DETECTION_COUNT = 3 (frames avant lock)")
    print("   LOCK_SWITCH_THRESHOLD = 150 (distance switch)")
    print("   TARGET_LOCK_ENABLED = True/False")
    print("")
    print("⌨️ ESC → Quitter")
    print("=" * 60)

    Thread(target=detect_loop, daemon=True).start()
    Thread(target=lambda: keyboard.Listener(on_press=on_press).start(), daemon=True).start()

    overlay_instance = Overlay()
    overlay_instance.run()
