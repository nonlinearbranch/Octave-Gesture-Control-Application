import subprocess
import webbrowser
import os


def open_vscode():
    subprocess.Popen("code", shell=True)


def open_browser():
    webbrowser.open("https://www.google.com")


def open_folder(path):
    os.startfile(path)
