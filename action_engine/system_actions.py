import os
import time

last_call = {}
cooldown = 2.0


def can_run(name):
    now = time.time()
    if name not in last_call:
        last_call[name] = 0
    if now - last_call[name] > cooldown:
        last_call[name] = now
        return True
    return False


def play_pause():
    if can_run("PLAY"):
        os.system("nircmd sendkeypress space")


def mute():
    if can_run("MUTE"):
        os.system("nircmd mutesysvolume 2")
