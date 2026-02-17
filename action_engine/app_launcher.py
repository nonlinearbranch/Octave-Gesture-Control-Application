import subprocess
import webbrowser
import os
import shutil


def open_vscode():
    if shutil.which("code"):
        subprocess.Popen("code", shell=True)
    elif os.path.exists("C:\\Program Files\\Microsoft VS Code\\Code.exe"):
        subprocess.Popen("\"C:\\Program Files\\Microsoft VS Code\\Code.exe\"", shell=True)


def open_browser():
    webbrowser.open("https://www.google.com")


def open_folder(path):
    os.startfile(path)


def _try_launch(command):
    try:
        subprocess.Popen(command, shell=True)
        return True
    except Exception:
        return False


def open_app(target):
    if not target:
        return False

    t = str(target).strip()
    low = t.lower()

    aliases = {
        "ms word": ["winword", "start \"\" winword"],
        "word": ["winword", "start \"\" winword"],
        "microsoft word": ["winword", "start \"\" winword"],
        "notepad": ["notepad", "start \"\" notepad"],
        "calculator": ["calc", "start \"\" calc"],
        "paint": ["mspaint", "start \"\" mspaint"],
        "chrome": ["chrome", "start \"\" chrome"],
        "edge": ["msedge", "start \"\" msedge"],
        "vscode": ["code", "\"C:\\Program Files\\Microsoft VS Code\\Code.exe\""]
    }

    if os.path.exists(t):
        return _try_launch(f"\"{t}\"")

    candidates = aliases.get(low, [t])
    for c in candidates:
        exe = c.split()[0].strip("\"")
        if "\\" in exe and os.path.exists(exe):
            if _try_launch(c):
                return True
        elif shutil.which(exe):
            if _try_launch(c):
                return True
        elif c.startswith("start "):
            if _try_launch(c):
                return True

    if low.endswith(".exe"):
        return _try_launch(f"start \"\" {low}")

    return _try_launch(f"start \"\" {t}")
