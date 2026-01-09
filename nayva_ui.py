import customtkinter as ctk
import psutil
import tkinter as tk
from tkinter import Canvas
import json
import os

# Chemin robuste vers settings.json (même dossier que le .py)
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

# Valeurs par défaut
DEFAULT_SETTINGS = {
    "autoshoot_enabled": False,
    "aimassist_enabled": False,
    "conf_autoshoot": 0.60,
    "conf_aimassist": 0.60,
    "aimassist_speed": 0.25
}

# Charger ou créer les settings
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {
                    "autoshoot_enabled": data.get("autoshoot_enabled", False),
                    "aimassist_enabled": data.get("aimassist_enabled", False),
                    "conf_autoshoot": data.get("conf_autoshoot", 0.60),
                    "conf_aimassist": data.get("conf_aimassist", 0.60),
                    "aimassist_speed": data.get("aimassist_speed", 0.25)
                }
        except Exception as e:
            print(f"Erreur lecture settings.json : {e} → valeurs par défaut")
    
    # Création avec valeurs par défaut
    save_settings(DEFAULT_SETTINGS)
    return DEFAULT_SETTINGS.copy()


def save_settings(settings_dict):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings_dict, f, indent=4)
    except Exception as e:
        print(f"Erreur sauvegarde settings: {e}")


# Charger au démarrage
settings = load_settings()

autoshoot_enabled = settings["autoshoot_enabled"]
aimassist_enabled = settings["aimassist_enabled"]
conf_autoshoot    = settings["conf_autoshoot"]
conf_aimassist    = settings["conf_aimassist"]
aimassist_speed   = settings["aimassist_speed"]


# Overlay Roblox (version STABLE sans clignotement)
overlay = None
overlay_frame = None
overlay_labels = []


def create_or_update_overlay():
    global overlay, overlay_frame, overlay_labels
    
    roblox_running = any("Roblox" in p.name() or "RobloxPlayer" in p.name() for p in psutil.process_iter(['name']))
    
    if not roblox_running or (not autoshoot_enabled and not aimassist_enabled):
        if overlay is not None:
            try:
                overlay.withdraw()  # Cacher sans détruire
            except:
                pass
        return
    
    # Créer seulement la première fois
    if overlay is None:
        overlay = tk.Toplevel()
        overlay.overrideredirect(True)
        overlay.attributes('-topmost', True)
        overlay.attributes('-alpha', 0.75)
        overlay.configure(bg='black')
        
        screen_width = overlay.winfo_screenwidth()
        overlay.geometry(f"180x100+{screen_width-210}+35")
        
        overlay_frame = tk.Frame(overlay, bg="#111111", bd=1, relief="solid")
        overlay_frame.pack(padx=8, pady=8, fill="both", expand=True)
    
    # Supprimer les anciens labels
    for lbl in overlay_labels:
        lbl.destroy()
    overlay_labels.clear()
    
    # Ajouter les nouveaux labels
    if autoshoot_enabled:
        lbl = tk.Label(overlay_frame, text="AUTO-SHOOT ON", font=("Helvetica", 11, "bold"), fg="#4ade80", bg="#111111")
        lbl.pack(anchor="w", padx=12, pady=4)
        overlay_labels.append(lbl)
    
    if aimassist_enabled:
        lbl = tk.Label(overlay_frame, text="AIM ASSIST ON", font=("Helvetica", 11, "bold"), fg="#a78bfa", bg="#111111")
        lbl.pack(anchor="w", padx=12, pady=4)
        overlay_labels.append(lbl)
    
    # Ajuster taille selon nombre de lignes
    num_lines = len(overlay_labels)
    screen_width = overlay.winfo_screenwidth()
    if num_lines == 1:
        overlay.geometry(f"180x60+{screen_width-210}+35")
    else:  # 2 lignes
        overlay.geometry(f"180x100+{screen_width-210}+35")
    
    overlay.deiconify()  # S'assurer qu'elle est visible


def check_roblox_loop():
    create_or_update_overlay()
    root.after(2500, check_roblox_loop)


# Sauvegarde après changement
def save_current_settings():
    current = {
        "autoshoot_enabled": autoshoot_enabled,
        "aimassist_enabled": aimassist_enabled,
        "conf_autoshoot": conf_autoshoot,
        "conf_aimassist": conf_aimassist,
        "aimassist_speed": aimassist_speed
    }
    save_settings(current)


# Callbacks
def toggle_autoshoot():
    global autoshoot_enabled
    autoshoot_enabled = not autoshoot_enabled
    create_or_update_overlay()
    save_current_settings()
    
    if autoshoot_enabled:
        auto_status_badge_frame.configure(fg_color="#1e2a22", border_color="#4ade80")
        auto_status_badge.configure(text="● ONLINE", text_color="#4ade80")
        section_auto.configure(border_color="#4ade80")
        toggle_auto_btn.configure(text="DISABLE", fg_color="#3b82f6", hover_color="#2563eb", border_color="#3b82f6")
        auto_indicator.configure(fg_color="#4ade80")
    else:
        auto_status_badge_frame.configure(fg_color="#1f1f1f", border_color="#444")
        auto_status_badge.configure(text="○ OFFLINE", text_color="#9ca3af")
        section_auto.configure(border_color="#444")
        toggle_auto_btn.configure(text="ENABLE", fg_color="#6b7280", hover_color="#4b5563", border_color="#6b7280")
        auto_indicator.configure(fg_color="#444")
    
    update_status_label()


def toggle_aimassist():
    global aimassist_enabled
    aimassist_enabled = not aimassist_enabled
    create_or_update_overlay()
    save_current_settings()
    
    if aimassist_enabled:
        aim_status_badge_frame.configure(fg_color="#1e2a22", border_color="#4ade80")
        aim_status_badge.configure(text="● ONLINE", text_color="#4ade80")
        section_aim.configure(border_color="#4ade80")
        toggle_aim_btn.configure(text="DISABLE", fg_color="#3b82f6", hover_color="#2563eb", border_color="#3b82f6")
        aim_indicator.configure(fg_color="#4ade80")
    else:
        aim_status_badge_frame.configure(fg_color="#1f1f1f", border_color="#444")
        aim_status_badge.configure(text="○ OFFLINE", text_color="#9ca3af")
        section_aim.configure(border_color="#444")
        toggle_aim_btn.configure(text="ENABLE", fg_color="#6b7280", hover_color="#4b5563", border_color="#6b7280")
        aim_indicator.configure(fg_color="#444")
    
    update_status_label()


def update_status_label():
    if autoshoot_enabled and aimassist_enabled:
        status_label.configure(text="AUTOSHOOT & AIMASSIST ACTIVE")
    elif autoshoot_enabled:
        status_label.configure(text="AUTO-SHOOT ENGAGED")
    elif aimassist_enabled:
        status_label.configure(text="AIM ASSIST LOCKED")
    else:
        status_label.configure(text="SYSTEM STANDBY")


def update_conf_auto(v):
    global conf_autoshoot
    conf_autoshoot = round(float(v), 2)
    percentage = int(conf_autoshoot * 100)
    conf_auto_value.configure(text=f"{percentage}%")
    
    if conf_autoshoot < 0.3:
        color = "#f87171"
        warning_label_auto.configure(text="Low threshold (<30%) → risk of false positives / wrong detections")
    elif conf_autoshoot > 0.80:
        color = "#f87171"
        warning_label_auto.configure(text="High threshold (>80%) → risk of missed detections")
    else:
        color = "#4ade80"
        warning_label_auto.configure(text="")
    
    slider_auto.configure(progress_color=color)
    save_current_settings()


def update_conf_aim(v):
    global conf_aimassist
    conf_aimassist = round(float(v), 2)
    percentage = int(conf_aimassist * 100)
    conf_aim_value.configure(text=f"{percentage}%")
    
    if conf_aimassist < 0.3:
        color = "#f87171"
        warning_label_aim.configure(text="Low threshold (<30%) → risk of false positives / wrong detections")
    elif conf_aimassist > 0.80:
        color = "#f87171"
        warning_label_aim.configure(text="High threshold (>80%) → risk of missed detections")
    else:
        color = "#4ade80"
        warning_label_aim.configure(text="")
    
    slider_aim.configure(progress_color=color)
    save_current_settings()


def update_speed(v):
    global aimassist_speed
    aimassist_speed = max(0.05, round(float(v), 2))
    speed_value.configure(text=f"{aimassist_speed:.2f}x")
    
    if aimassist_speed < 0.15:
        color = "#60a5fa"
        txt = "SLOW"
    elif aimassist_speed < 0.35:
        color = "#38bdf8"
        txt = "MEDIUM"
    else:
        color = "#c084fc"
        txt = "FAST"
    
    slider_speed.configure(progress_color=color)
    speed_label.configure(text=f"SPEED: {txt}")
    save_current_settings()


# ================================================
#                INTERFACE
# ================================================
root = ctk.CTk()
root.title("Nayva AI")
root.geometry("560x820")
root.resizable(False, False)
root.configure(fg_color="#0f0f11")

bg_canvas = Canvas(root, bg="#0f0f11", highlightthickness=0)
bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

header_container = ctk.CTkFrame(root, fg_color="transparent")
header_container.pack(pady=(24, 16))
ctk.CTkLabel(header_container, text="NAYVA AI", font=("Helvetica", 28, "bold"), text_color="#e5e7eb").pack()

main_container = ctk.CTkFrame(root, fg_color="#111113", corner_radius=16, border_width=1, border_color="#1f2937")
main_container.pack(padx=16, pady=(0, 8), fill="both", expand=True)

scroll_frame = ctk.CTkScrollableFrame(main_container, fg_color="transparent")
scroll_frame.pack(padx=12, pady=12, fill="both", expand=True)

root.bind_all("<MouseWheel>", lambda e: scroll_frame._parent_canvas.yview_scroll(-int(e.delta / 5), "units"))

# ── AUTO SHOOT ───────────────────────────────────────
section_auto = ctk.CTkFrame(scroll_frame, fg_color="#17171a", corner_radius=12, border_width=1, border_color="#2d3748")
section_auto.pack(padx=8, pady=(8, 6), fill="x")

auto_header = ctk.CTkFrame(section_auto, fg_color="transparent")
auto_header.pack(fill="x", padx=16, pady=(12, 0))

auto_top = ctk.CTkFrame(auto_header, fg_color="transparent")
auto_top.pack(fill="x", pady=(8, 0))

auto_left = ctk.CTkFrame(auto_top, fg_color="transparent")
auto_left.pack(side="left")

title_row_auto = ctk.CTkFrame(auto_left, fg_color="transparent")
title_row_auto.pack(anchor="w")
auto_indicator = ctk.CTkFrame(title_row_auto, fg_color="#4b5563", width=10, height=10, corner_radius=5)
auto_indicator.pack(side="left", padx=(0,8))
ctk.CTkLabel(title_row_auto, text="AUTO SHOOT", font=("Helvetica", 18, "bold"), text_color="#e5e7eb").pack(side="left")

auto_status_badge_frame = ctk.CTkFrame(auto_left, fg_color="#1f2937", corner_radius=8, border_width=1, border_color="#374151")
auto_status_badge_frame.pack(anchor="w", pady=(8, 0))
auto_status_badge = ctk.CTkLabel(auto_status_badge_frame, text="○ OFFLINE", font=("Helvetica", 11), text_color="#9ca3af", padx=12, pady=4)
auto_status_badge.pack()

toggle_auto_btn = ctk.CTkButton(auto_top, text="ENABLE" if not autoshoot_enabled else "DISABLE", 
    command=toggle_autoshoot,
    font=("Helvetica", 13, "bold"), width=120, height=38, corner_radius=10,
    fg_color="#374151" if not autoshoot_enabled else "#3b82f6",
    hover_color="#4b5563" if not autoshoot_enabled else "#2563eb",
    text_color="white", border_width=1, border_color="#4b5563" if not autoshoot_enabled else "#3b82f6")
toggle_auto_btn.pack(side="right")

ctk.CTkFrame(section_auto, fg_color="#2d3748", height=1).pack(fill="x", padx=20, pady=12)

slider_cont_auto = ctk.CTkFrame(section_auto, fg_color="transparent")
slider_cont_auto.pack(fill="x", padx=20, pady=(0,16))

ctk.CTkLabel(slider_cont_auto, text="CONFIDENCE", font=("Helvetica", 10), text_color="#9ca3af").pack(anchor="w")
conf_auto_value = ctk.CTkLabel(slider_cont_auto, text=f"{int(conf_autoshoot*100)}%", font=("Consolas", 18, "bold"), text_color="#e5e7eb")
conf_auto_value.pack(anchor="e", pady=(2,4))

slider_auto = ctk.CTkSlider(slider_cont_auto, from_=0, to=1, number_of_steps=100, height=20, corner_radius=10,
    progress_color="#4ade80", button_color="#ffffff", button_hover_color="#e5e7eb", fg_color="#2d3748",
    command=update_conf_auto)
slider_auto.set(conf_autoshoot)
slider_auto.pack(fill="x", pady=(2,4))

# Traits 20% et 80% directement sur le slider
marker_20_auto = ctk.CTkFrame(slider_auto, fg_color="#6b7280", width=2, height=20, corner_radius=0)
marker_20_auto.place(relx=0.2, rely=0.5, anchor="center")

marker_80_auto = ctk.CTkFrame(slider_auto, fg_color="#6b7280", width=2, height=20, corner_radius=0)
marker_80_auto.place(relx=0.8, rely=0.5, anchor="center")

warning_label_auto = ctk.CTkLabel(slider_cont_auto, text="", font=("Helvetica", 10), text_color="#ef4444")
warning_label_auto.pack(anchor="w", pady=(4,0))

# ── AIM ASSIST ───────────────────────────────────────
section_aim = ctk.CTkFrame(scroll_frame, fg_color="#17171a", corner_radius=12, border_width=1, border_color="#2d3748")
section_aim.pack(padx=8, pady=8, fill="x")

aim_header = ctk.CTkFrame(section_aim, fg_color="transparent")
aim_header.pack(fill="x", padx=16, pady=(12, 0))

aim_top = ctk.CTkFrame(aim_header, fg_color="transparent")
aim_top.pack(fill="x", pady=(8, 0))

aim_left = ctk.CTkFrame(aim_top, fg_color="transparent")
aim_left.pack(side="left")

title_row_aim = ctk.CTkFrame(aim_left, fg_color="transparent")
title_row_aim.pack(anchor="w")
aim_indicator = ctk.CTkFrame(title_row_aim, fg_color="#4b5563", width=10, height=10, corner_radius=5)
aim_indicator.pack(side="left", padx=(0,8))
ctk.CTkLabel(title_row_aim, text="AIM ASSIST", font=("Helvetica", 18, "bold"), text_color="#e5e7eb").pack(side="left")

aim_status_badge_frame = ctk.CTkFrame(aim_left, fg_color="#1f2937", corner_radius=8, border_width=1, border_color="#374151")
aim_status_badge_frame.pack(anchor="w", pady=(8, 0))
aim_status_badge = ctk.CTkLabel(aim_status_badge_frame, text="○ OFFLINE", font=("Helvetica", 11), text_color="#9ca3af", padx=12, pady=4)
aim_status_badge.pack()

toggle_aim_btn = ctk.CTkButton(aim_top, text="ENABLE" if not aimassist_enabled else "DISABLE", 
    command=toggle_aimassist,
    font=("Helvetica", 13, "bold"), width=120, height=38, corner_radius=10,
    fg_color="#374151" if not aimassist_enabled else "#3b82f6",
    hover_color="#4b5563" if not aimassist_enabled else "#2563eb",
    text_color="white", border_width=1, border_color="#4b5563" if not aimassist_enabled else "#3b82f6")
toggle_aim_btn.pack(side="right")

ctk.CTkFrame(section_aim, fg_color="#2d3748", height=1).pack(fill="x", padx=20, pady=12)

slider_cont_aim = ctk.CTkFrame(section_aim, fg_color="transparent")
slider_cont_aim.pack(fill="x", padx=20, pady=(0,12))

ctk.CTkLabel(slider_cont_aim, text="CONFIDENCE", font=("Helvetica", 10), text_color="#9ca3af").pack(anchor="w")
conf_aim_value = ctk.CTkLabel(slider_cont_aim, text=f"{int(conf_aimassist*100)}%", font=("Consolas", 18, "bold"), text_color="#e5e7eb")
conf_aim_value.pack(anchor="e", pady=(2,4))

slider_aim = ctk.CTkSlider(slider_cont_aim, from_=0, to=1, number_of_steps=100, height=20, corner_radius=10,
    progress_color="#4ade80", button_color="#ffffff", button_hover_color="#e5e7eb", fg_color="#2d3748",
    command=update_conf_aim)
slider_aim.set(conf_aimassist)
slider_aim.pack(fill="x", pady=(2,4))

marker_20_aim = ctk.CTkFrame(slider_aim, fg_color="#6b7280", width=2, height=20, corner_radius=0)
marker_20_aim.place(relx=0.2, rely=0.5, anchor="center")

marker_80_aim = ctk.CTkFrame(slider_aim, fg_color="#6b7280", width=2, height=20, corner_radius=0)
marker_80_aim.place(relx=0.8, rely=0.5, anchor="center")

warning_label_aim = ctk.CTkLabel(slider_cont_aim, text="", font=("Helvetica", 10), text_color="#ef4444")
warning_label_aim.pack(anchor="w", pady=(4,0))

# ── TRACKING SPEED ────────────────────────────────────
ctk.CTkLabel(section_aim, text="TRACKING SPEED", font=("Helvetica", 16, "bold"), text_color="#e5e7eb").pack(pady=(12,6))

slider_cont_speed = ctk.CTkFrame(section_aim, fg_color="transparent")
slider_cont_speed.pack(fill="x", padx=20, pady=(0,16))

speed_top = ctk.CTkFrame(slider_cont_speed, fg_color="transparent")
speed_top.pack(fill="x")

speed_label = ctk.CTkLabel(speed_top, text="SPEED: MEDIUM", font=("Helvetica", 10), text_color="#9ca3af")
speed_label.pack(side="left")
speed_value = ctk.CTkLabel(speed_top, text=f"{aimassist_speed:.2f}x", font=("Consolas", 18, "bold"), text_color="#e5e7eb")
speed_value.pack(side="right")

slider_speed = ctk.CTkSlider(slider_cont_speed, from_=0.05, to=0.5, number_of_steps=45,
    height=20, corner_radius=10,
    progress_color="#60a5fa", button_color="#ffffff", button_hover_color="#e5e7eb", fg_color="#2d3748",
    command=update_speed)
slider_speed.set(aimassist_speed)
slider_speed.pack(fill="x")

# Status + footer
status_frame = ctk.CTkFrame(root, fg_color="#111113", height=48, corner_radius=0, border_width=1, border_color="#1f2937")
status_frame.pack(side="bottom", fill="x")
status_label = ctk.CTkLabel(status_frame, text="SYSTEM STANDBY", font=("Helvetica", 12, "bold"), text_color="#e5e7eb")
status_label.pack(pady=14)

footer = ctk.CTkFrame(root, fg_color="transparent", height=24)
footer.pack(side="bottom", fill="x")
ctk.CTkLabel(footer, text="MADE BY JEXX & SEBA", font=("Helvetica", 9), text_color="#6b7280").pack(pady=4)

# Initialisation visuelle des états chargés
if autoshoot_enabled:
    toggle_autoshoot()
    toggle_autoshoot()  # Appliquer l'état chargé

if aimassist_enabled:
    toggle_aimassist()
    toggle_aimassist()

# Lancement boucle détection Roblox
root.after(1000, check_roblox_loop)

root.mainloop()
