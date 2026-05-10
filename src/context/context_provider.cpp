#include "context/context_provider.hpp"

#include <cctype>
#include <chrono>
#include <string>
#include <thread>

#include "core/logging.hpp"

#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#include <mmdeviceapi.h>
#include <audiopolicy.h>
#endif

namespace spider::context {

#ifdef _WIN32
namespace {

std::string get_foreground_process_name() {
    const HWND foreground = GetForegroundWindow();
    if (foreground == nullptr) {
        return {};
    }

    DWORD process_id = 0;
    GetWindowThreadProcessId(foreground, &process_id);
    if (process_id == 0) {
        return {};
    }

    const HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, process_id);
    if (process == nullptr) {
        return {};
    }

    char path[MAX_PATH]{};
    DWORD path_size = MAX_PATH;
    std::string name;
    if (QueryFullProcessImageNameA(process, 0, path, &path_size)) {
        name = path;
        const auto slash = name.find_last_of("\\/");
        if (slash != std::string::npos) {
            name = name.substr(slash + 1);
        }
        for (auto& ch : name) {
            ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
        }
    }

    CloseHandle(process);
    return name;
}

std::string get_foreground_window_title() {
    const HWND foreground = GetForegroundWindow();
    if (foreground == nullptr) {
        return {};
    }

    char title[256]{};
    GetWindowTextA(foreground, title, sizeof(title));
    return title;
}

core::ContextMode classify_process(const std::string& process_name) {
    if (process_name.find("powerpnt") != std::string::npos ||
        process_name.find("keynote") != std::string::npos ||
        process_name.find("impress") != std::string::npos) {
        return core::ContextMode::Presentation;
    }

    if (process_name.find("zoom") != std::string::npos ||
        process_name.find("teams") != std::string::npos ||
        process_name.find("webex") != std::string::npos ||
        process_name.find("slack") != std::string::npos ||
        process_name.find("discord") != std::string::npos) {
        return core::ContextMode::Conferencing;
    }

    if (process_name.find("photoshop") != std::string::npos ||
        process_name.find("illustrator") != std::string::npos ||
        process_name.find("figma") != std::string::npos ||
        process_name.find("blender") != std::string::npos ||
        process_name.find("sketch") != std::string::npos) {
        return core::ContextMode::Design;
    }

    if (process_name.find("steam") != std::string::npos ||
        process_name.find("epicgameslauncher") != std::string::npos ||
        process_name.find("riotclient") != std::string::npos ||
        process_name.find("valorant") != std::string::npos ||
        process_name.find("cs2") != std::string::npos ||
        process_name.find("dota") != std::string::npos) {
        return core::ContextMode::Gaming;
    }

    if (process_name.find("chrome") != std::string::npos ||
        process_name.find("firefox") != std::string::npos ||
        process_name.find("msedge") != std::string::npos ||
        process_name.find("opera") != std::string::npos ||
        process_name.find("brave") != std::string::npos ||
        process_name.find("electron") != std::string::npos ||
        process_name.find("spider-ui") != std::string::npos ||
        process_name.find("node") != std::string::npos) {
        return core::ContextMode::Browser;
    }

    if (process_name.find("vlc") != std::string::npos ||
        process_name.find("spotify") != std::string::npos ||
        process_name.find("wmplayer") != std::string::npos ||
        process_name.find("groove") != std::string::npos ||
        process_name.find("itunes") != std::string::npos ||
        process_name.find("mpv") != std::string::npos) {
        return core::ContextMode::Media;
    }

    if (process_name.find("code") != std::string::npos ||
        process_name.find("devenv") != std::string::npos ||
        process_name.find("notepad") != std::string::npos ||
        process_name.find("sublime") != std::string::npos ||
        process_name.find("idea") != std::string::npos ||
        process_name.find("clion") != std::string::npos) {
        return core::ContextMode::Editor;
    }

    return core::ContextMode::Desktop;
}

bool check_is_audio_playing() {
    bool is_playing = false;
    
    IMMDeviceEnumerator* device_enumerator = nullptr;
    HRESULT hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL, __uuidof(IMMDeviceEnumerator), (void**)&device_enumerator);
    if (SUCCEEDED(hr)) {
        IMMDevice* default_device = nullptr;
        hr = device_enumerator->GetDefaultAudioEndpoint(eRender, eMultimedia, &default_device);
        if (SUCCEEDED(hr)) {
            IAudioSessionManager2* session_manager = nullptr;
            hr = default_device->Activate(__uuidof(IAudioSessionManager2), CLSCTX_ALL, nullptr, (void**)&session_manager);
            if (SUCCEEDED(hr)) {
                IAudioSessionEnumerator* session_enumerator = nullptr;
                hr = session_manager->GetSessionEnumerator(&session_enumerator);
                if (SUCCEEDED(hr)) {
                    int session_count = 0;
                    hr = session_enumerator->GetCount(&session_count);
                    if (SUCCEEDED(hr)) {
                        for (int i = 0; i < session_count; ++i) {
                            IAudioSessionControl* session_control = nullptr;
                            hr = session_enumerator->GetSession(i, &session_control);
                            if (SUCCEEDED(hr)) {
                                AudioSessionState state;
                                hr = session_control->GetState(&state);
                                if (SUCCEEDED(hr) && state == AudioSessionStateActive) {
                                    is_playing = true;
                                    session_control->Release();
                                    break;
                                }
                                session_control->Release();
                            }
                        }
                    }
                    session_enumerator->Release();
                }
                session_manager->Release();
            }
            default_device->Release();
        }
        device_enumerator->Release();
    }
    
    return is_playing;
}

}  // namespace
#endif

ContextProvider::ContextProvider(bus::Publisher<core::ContextSnapshot> publisher)
    : publisher_(std::move(publisher)) {}

void ContextProvider::run(std::atomic<bool>& running) {
    std::uint64_t sequence_number = 1U;
    core::ContextMode previous_mode = core::ContextMode::Unknown;
    bool previous_audio = false;

    std::string persistent_media_app = "";
    auto last_audio_time = std::chrono::steady_clock::now();

#ifdef _WIN32
    HRESULT hr_coinit = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    bool co_init_success = SUCCEEDED(hr_coinit) || hr_coinit == RPC_E_CHANGED_MODE;
#endif

    while (running.load()) {
#ifdef _WIN32
        const std::string process_name = get_foreground_process_name();
        const std::string window_title = get_foreground_window_title();
        core::ContextMode mode = process_name.empty()
            ? core::ContextMode::Desktop
            : classify_process(process_name);

        bool is_playing = check_is_audio_playing();
        auto now = std::chrono::steady_clock::now();
        
        if (is_playing) {
            persistent_media_app = process_name;
            last_audio_time = now;
        }
        
        if (process_name == persistent_media_app && 
            std::chrono::duration_cast<std::chrono::minutes>(now - last_audio_time).count() < 15) {
            if (mode == core::ContextMode::Browser || mode == core::ContextMode::Desktop) {
                mode = core::ContextMode::Media;
            }
        }
#else
        const std::string process_name = "unknown";
        const std::string window_title = "Unknown";
        core::ContextMode mode = core::ContextMode::Desktop;
        bool is_playing = false;
#endif

        if (mode != previous_mode || is_playing != previous_audio) {
            core::ContextSnapshot snapshot{};
            snapshot.header.sequence_number = sequence_number++;
            snapshot.header.timestamp = std::chrono::steady_clock::now();
            snapshot.app_id = process_name;
            snapshot.window_title = window_title;
            snapshot.context_mode = mode;
            snapshot.is_audio_playing = is_playing;

            if (publisher_.publish(snapshot)) {
                core::log_line("[Context] ", core::to_string(mode), 
                    is_playing ? " [Audio Active]" : "", 
                    " (", process_name, ")");
            }

            previous_mode = mode;
            previous_audio = is_playing;
        }

        for (int step = 0; step < 5 && running.load(); ++step) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }

#ifdef _WIN32
    if (co_init_success) {
        CoUninitialize();
    }
#endif
}

}  // namespace spider::context
