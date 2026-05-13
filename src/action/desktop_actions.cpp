#include "action/desktop_actions.hpp"

#include <algorithm>
#include <cmath>
#include <string>
#include <atomic>
#include <chrono>
#include <thread>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <physicalmonitorenumerationapi.h>
#include <highlevelmonitorconfigurationapi.h>
#endif

namespace spider::action::desktop_actions {

#ifdef _WIN32
namespace {

void send_inputs(INPUT* inputs, const int count) {
    if (count > 0) {
        SendInput(count, inputs, sizeof(INPUT));
    }
}

void send_key_press(const WORD key) {
    INPUT inputs[2]{};
    inputs[0].type = INPUT_KEYBOARD;
    inputs[0].ki.wVk = key;
    inputs[1].type = INPUT_KEYBOARD;
    inputs[1].ki.wVk = key;
    inputs[1].ki.dwFlags = KEYEVENTF_KEYUP;
    send_inputs(inputs, 2);
}

void send_key_combo(const WORD modifiers[], const int modifier_count, const WORD key) {
    INPUT inputs[8]{};
    int index = 0;
    for (int i = 0; i < modifier_count; ++i) {
        inputs[index].type = INPUT_KEYBOARD;
        inputs[index].ki.wVk = modifiers[i];
        ++index;
    }
    inputs[index].type = INPUT_KEYBOARD;
    inputs[index].ki.wVk = key;
    ++index;
    inputs[index].type = INPUT_KEYBOARD;
    inputs[index].ki.wVk = key;
    inputs[index].ki.dwFlags = KEYEVENTF_KEYUP;
    ++index;
    for (int i = modifier_count - 1; i >= 0; --i) {
        inputs[index].type = INPUT_KEYBOARD;
        inputs[index].ki.wVk = modifiers[i];
        inputs[index].ki.dwFlags = KEYEVENTF_KEYUP;
        ++index;
    }
    send_inputs(inputs, index);
}

void send_mouse_click(const DWORD down_flag, const DWORD up_flag) {
    INPUT inputs[2]{};
    inputs[0].type = INPUT_MOUSE;
    inputs[0].mi.dwFlags = down_flag;
    inputs[1].type = INPUT_MOUSE;
    inputs[1].mi.dwFlags = up_flag;
    send_inputs(inputs, 2);
}

void send_wheel(const LONG amount) {
    INPUT input{};
    input.type = INPUT_MOUSE;
    input.mi.dwFlags = MOUSEEVENTF_WHEEL;
    input.mi.mouseData = amount;
    send_inputs(&input, 1);
}

void open_target(const char* target) {
    std::string command = "cmd.exe /c start \"\" \"";
    command += target;
    command += "\"";
    WinExec(command.c_str(), SW_SHOWNORMAL);
}

int compute_step_count(const float delta) {
    const float magnitude = std::fabs(delta);
    if (magnitude < 0.05F) {
        return 0;
    }
    const int rounded = static_cast<int>(std::round(magnitude * 4.0F));
    return rounded < 1 ? 1 : rounded;
}

void adjust_brightness_step_powershell(const int steps) {
    static std::atomic<int> current_laptop_brightness{-1};
    static auto last_update = std::chrono::steady_clock::now();
    
    // Default assumption if we don't know the starting brightness
    if (current_laptop_brightness == -1) {
        current_laptop_brightness = 50; 
    }

    int target = current_laptop_brightness + (steps * 5);
    target = std::clamp(target, 0, 100);
    
    // Only update if there's an actual change
    if (target == current_laptop_brightness) {
        return;
    }
    
    current_laptop_brightness = target;

    // Throttle PowerShell executions to avoid freezing the system
    auto now = std::chrono::steady_clock::now();
    if (std::chrono::duration_cast<std::chrono::milliseconds>(now - last_update).count() < 150) {
        return; 
    }
    last_update = now;

    // Execute asynchronously to not block the gesture processing loop
    std::thread([target]() {
        std::string cmd = "powershell.exe -WindowStyle Hidden -Command \"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, " + std::to_string(target) + ")\"";
        WinExec(cmd.c_str(), SW_HIDE);
    }).detach();
}

void adjust_brightness_step(const int steps) {
    const HMONITOR monitor = MonitorFromWindow(GetDesktopWindow(), MONITOR_DEFAULTTOPRIMARY);
    if (!monitor) {
        return;
    }

    DWORD count = 0;
    if (!GetNumberOfPhysicalMonitorsFromHMONITOR(monitor, &count) || count == 0) {
        adjust_brightness_step_powershell(steps);
        return;
    }

    PHYSICAL_MONITOR physical{};
    if (!GetPhysicalMonitorsFromHMONITOR(monitor, 1, &physical)) {
        adjust_brightness_step_powershell(steps);
        return;
    }

    DWORD min_brightness = 0;
    DWORD cur_brightness = 0;
    DWORD max_brightness = 0;
    bool ddc_success = false;
    
    if (GetMonitorBrightness(physical.hPhysicalMonitor, &min_brightness, &cur_brightness, &max_brightness)) {
        const int range = static_cast<int>(max_brightness - min_brightness);
        const int increment = std::max(1, range / 20);
        int target = static_cast<int>(cur_brightness) + steps * increment;
        target = std::clamp(target, static_cast<int>(min_brightness), static_cast<int>(max_brightness));
        if (SetMonitorBrightness(physical.hPhysicalMonitor, static_cast<DWORD>(target))) {
            ddc_success = true;
        }
    }

    DestroyPhysicalMonitors(1, &physical);
    
    // If DDC/CI failed (e.g. laptop display), fall back to PowerShell WMI method
    if (!ddc_success) {
        adjust_brightness_step_powershell(steps);
    }
}

}  // namespace
#endif

bool execute_discrete_action(const std::string& action_id) {
#ifndef _WIN32
    (void)action_id;
    return false;
#else
    if (action_id == "None" || action_id.empty()) return false;
    if (action_id == "Click") {
        send_mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP);
        return true;
    }
    if (action_id == "DoubleClick") {
        send_mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP);
        send_mouse_click(MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP);
        return true;
    }
    if (action_id == "RightClick") {
        send_mouse_click(MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP);
        return true;
    }
    if (action_id == "MiddleClick") {
        send_mouse_click(MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP);
        return true;
    }
    if (action_id == "ScrollUp") {
        send_wheel(WHEEL_DELTA);
        return true;
    }
    if (action_id == "ScrollDown") {
        send_wheel(-WHEEL_DELTA);
        return true;
    }
    if (action_id == "ConfirmEnter" || action_id == "Confirm / Enter") {
        send_key_press(VK_RETURN);
        return true;
    }
    if (action_id == "Escape") {
        send_key_press(VK_ESCAPE);
        return true;
    }
    if (action_id == "MuteToggle" || action_id == "Mute / Unmute") {
        send_key_press(VK_VOLUME_MUTE);
        return true;
    }
    if (action_id == "VolumeUp" || action_id == "Volume Up") {
        send_key_press(VK_VOLUME_UP);
        return true;
    }
    if (action_id == "VolumeDown" || action_id == "Volume Down") {
        send_key_press(VK_VOLUME_DOWN);
        return true;
    }
    if (action_id == "NextTrack" || action_id == "Next / Previous") {
        send_key_press(VK_MEDIA_NEXT_TRACK);
        return true;
    }
    if (action_id == "PrevTrack") {
        send_key_press(VK_MEDIA_PREV_TRACK);
        return true;
    }
    if (action_id == "PlayPause" || action_id == "Play / Pause") {
        send_key_press(VK_MEDIA_PLAY_PAUSE);
        return true;
    }
    if (action_id == "Undo") {
        const WORD modifiers[] = {VK_CONTROL};
        send_key_combo(modifiers, 1, 'Z');
        return true;
    }
    if (action_id == "Redo") {
        const WORD modifiers[] = {VK_CONTROL};
        send_key_combo(modifiers, 1, 'Y');
        return true;
    }
    if (action_id == "SwitchTab") {
        const WORD modifiers[] = {VK_CONTROL};
        send_key_combo(modifiers, 1, VK_TAB);
        return true;
    }
    if (action_id == "SwitchTabPrev") {
        const WORD modifiers[] = {VK_CONTROL, VK_SHIFT};
        send_key_combo(modifiers, 2, VK_TAB);
        return true;
    }
    if (action_id == "SwitchWindow") {
        const WORD modifiers[] = {VK_MENU};
        send_key_combo(modifiers, 1, VK_TAB);
        return true;
    }
    if (action_id == "GoBack" || action_id == "Navigate Back") {
        const WORD modifiers[] = {VK_MENU};
        send_key_combo(modifiers, 1, VK_LEFT);
        return true;
    }
    if (action_id == "GoForward" || action_id == "Navigate Forward") {
        const WORD modifiers[] = {VK_MENU};
        send_key_combo(modifiers, 1, VK_RIGHT);
        return true;
    }
    if (action_id == "PrevSlide") {
        send_key_press(VK_LEFT);
        return true;
    }
    if (action_id == "NextSlide") {
        send_key_press(VK_RIGHT);
        return true;
    }
    if (action_id == "ToggleFullscreenVideo") {
        send_key_press('F');
        return true;
    }
    if (action_id == "ToggleStartMenu") {
        send_key_press(VK_LWIN);
        return true;
    }
    if (action_id == "Minimize Window") {
        const WORD modifiers[] = {VK_LWIN};
        send_key_combo(modifiers, 1, 'M');
        return true;
    }
    if (action_id == "OpenBrowser") {
        open_target("https://www.google.com");
        return true;
    }
    if (action_id == "OpenVSCode") {
        open_target("code");
        return true;
    }
    if (action_id == "LockScreen" || action_id == "Power Command") {
        LockWorkStation();
        return true;
    }
    if (action_id == "Screenshot") {
        const WORD modifiers[] = {VK_LWIN, VK_SHIFT};
        send_key_combo(modifiers, 2, 'S');
        return true;
    }
    if (action_id == "ZoomIn") {
        const WORD modifiers[] = {VK_CONTROL};
        send_key_combo(modifiers, 1, VK_ADD);
        return true;
    }
    if (action_id == "ZoomOut") {
        const WORD modifiers[] = {VK_CONTROL};
        send_key_combo(modifiers, 1, VK_SUBTRACT);
        return true;
    }
    if (action_id == "BrushSizeIncrease") {
        send_key_press(VK_OEM_6);
        return true;
    }
    if (action_id == "BrushSizeDecrease") {
        send_key_press(VK_OEM_4);
        return true;
    }
    if (action_id == "WeaponNext") {
        send_wheel(-WHEEL_DELTA);
        return true;
    }
    if (action_id == "WeaponPrev") {
        send_wheel(WHEEL_DELTA);
        return true;
    }
    return false;
#endif
}

void apply_continuous_update(const core::ContinuousDomain domain, const float delta) {
#ifndef _WIN32
    (void)domain;
    (void)delta;
#else
    const int step_count = compute_step_count(delta);
    if (step_count <= 0) {
        return;
    }

    switch (domain) {
    case core::ContinuousDomain::Scroll:
    case core::ContinuousDomain::ScrollSpeed:
        for (int index = 0; index < step_count; ++index) {
            send_wheel(delta >= 0.0F ? WHEEL_DELTA / 2 : -WHEEL_DELTA / 2);
        }
        break;
    case core::ContinuousDomain::Zoom: {
        const WORD modifiers[] = {VK_CONTROL};
        for (int index = 0; index < step_count; ++index) {
            send_key_combo(modifiers, 1, delta >= 0.0F ? VK_ADD : VK_SUBTRACT);
        }
        break;
    }
    case core::ContinuousDomain::Volume:
        for (int index = 0; index < step_count; ++index) {
            send_key_press(delta >= 0.0F ? VK_VOLUME_UP : VK_VOLUME_DOWN);
        }
        break;
    case core::ContinuousDomain::Brightness:
        adjust_brightness_step(delta >= 0.0F ? step_count : -step_count);
        break;
    case core::ContinuousDomain::Timeline:
        for (int index = 0; index < step_count; ++index) {
            send_key_press(delta >= 0.0F ? VK_RIGHT : VK_LEFT);
        }
        break;
    case core::ContinuousDomain::Cursor:
    case core::ContinuousDomain::Adjust:
    default:
        break;
    }
#endif
}

const char* describe_action(const std::string& action_id) {
    if (action_id == "Click") return "Selecting...";
    if (action_id == "DoubleClick") return "Double Clicking...";
    if (action_id == "RightClick") return "Right Clicking...";
    if (action_id == "MiddleClick") return "Middle Clicking...";
    if (action_id == "ScrollUp") return "Scrolling Up...";
    if (action_id == "ScrollDown") return "Scrolling Down...";
    if (action_id == "VolumeUp") return "Volume Up";
    if (action_id == "VolumeDown") return "Volume Down";
    if (action_id == "ZoomIn") return "Zooming In";
    if (action_id == "ZoomOut") return "Zooming Out";
    if (action_id == "GoBack") return "Navigating Back";
    if (action_id == "GoForward") return "Navigating Forward";
    if (action_id == "OpenVSCode") return "Opening VS Code";
    if (action_id == "OpenBrowser") return "Opening Browser";
    if (action_id == "Escape") return "Cancelling...";
    if (action_id == "ConfirmEnter") return "Confirming...";
    if (action_id == "Undo") return "Undoing...";
    if (action_id == "Redo") return "Redoing...";
    if (action_id == "PrevSlide") return "Previous Slide";
    if (action_id == "NextSlide") return "Next Slide";
    if (action_id == "ToggleFullscreenVideo") return "Toggling Fullscreen";
    if (action_id == "ToggleStartMenu") return "Opening Start Menu";
    if (action_id == "BrushSizeIncrease") return "Increasing Brush Size";
    if (action_id == "BrushSizeDecrease") return "Decreasing Brush Size";
    if (action_id == "WeaponNext") return "Cycling Next";
    if (action_id == "WeaponPrev") return "Cycling Previous";
    if (action_id == "SwitchTabPrev") return "Previous Tab";
    return "Executing Action...";
}

}  // namespace spider::action::desktop_actions
