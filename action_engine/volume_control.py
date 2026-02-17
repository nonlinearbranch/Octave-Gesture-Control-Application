from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL

devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(
    IAudioEndpointVolume._iid_,
    CLSCTX_ALL,
    None
)

volume = cast(interface, POINTER(IAudioEndpointVolume))


def get_volume():
    return volume.GetMasterVolumeLevelScalar()


def set_volume(value):
    if value < 0:
        value = 0
    if value > 1:
        value = 1

    volume.SetMasterVolumeLevelScalar(value, None)


def increase(step=0.05):
    current = get_volume()
    set_volume(current + step)


def decrease(step=0.05):
    current = get_volume()
    set_volume(current - step)


def mute_toggle():
    volume.SetMute(not volume.GetMute(), None)
