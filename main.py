import os
import sys
import subprocess
import urllib.request
import tempfile

# URLs GitHub (raw)
UI_URL = "https://raw.githubusercontent.com/JexxDev/Nayva/refs/heads/main/nayva_ui.py"
AI_URL = "https://raw.githubusercontent.com/JexxDev/Nayva/refs/heads/main/nayva_ai.py"

def download(url, path):
    try:
        urllib.request.urlretrieve(url, path)
    except Exception:
        sys.exit(1)

def main():
    # Dossier temporaire système (ex: C:\Users\...\AppData\Local\Temp\Nayva)
    temp_dir = os.path.join(tempfile.gettempdir(), "Nayva")
    os.makedirs(temp_dir, exist_ok=True)

    ui_path = os.path.join(temp_dir, "nayva_ui.py")
    ai_path = os.path.join(temp_dir, "nayva_ai.py")

    # Télécharger les scripts (écrasés à chaque lancement)
    download(UI_URL, ui_path)
    download(AI_URL, ai_path)

    # Python embarqué dans l'exe
    python_exe = sys.executable

    # Lancer UI + IA
    subprocess.Popen([python_exe, ui_path], cwd=temp_dir)
    subprocess.Popen([python_exe, ai_path], cwd=temp_dir)

if __name__ == "__main__":
    main()
