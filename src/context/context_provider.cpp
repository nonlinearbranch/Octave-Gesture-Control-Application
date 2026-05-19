#include "context/context_provider.hpp"

#include <cctype>
#include <chrono>
#include <optional>
#include <string>
#include <utility>

#include "context/uia_helper.hpp"
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

ContextProvider* g_active_context_provider = nullptr;

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

ContextProvider::ContextProvider(
    bus::Publisher<core::ContextSnapshot> publisher,
    const std::string& config_path)
    : publisher_(std::move(publisher)),
      registry_(config_path) {}

void ContextProvider::run(std::atomic<bool>& running) {
    external_running_ = &running;
    running_.store(true);

#ifdef _WIN32
    thread_id_ = GetCurrentThreadId();

    MSG queue_init{};
    PeekMessage(&queue_init, nullptr, WM_USER, WM_USER, PM_NOREMOVE);

    HRESULT hr_coinit = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    const bool co_init_success = SUCCEEDED(hr_coinit) || hr_coinit == RPC_E_CHANGED_MODE;

    g_active_context_provider = this;

    foreground_hook_ = SetWinEventHook(
        EVENT_SYSTEM_FOREGROUND,
        EVENT_SYSTEM_FOREGROUND,
        nullptr,
        &ContextProvider::win_event_callback,
        0,
        0,
        WINEVENT_OUTOFCONTEXT);

    namechange_hook_ = SetWinEventHook(
        EVENT_OBJECT_NAMECHANGE,
        EVENT_OBJECT_NAMECHANGE,
        nullptr,
        &ContextProvider::win_event_callback,
        0,
        0,
        WINEVENT_OUTOFCONTEXT);

    audio_timer_id_ = SetTimer(nullptr, 0, 2000U, &ContextProvider::timer_callback);

    current_audio_state_.store(check_is_audio_playing());
    publish_context_snapshot(GetForegroundWindow(), current_audio_state_.load());

    while (running_.load() && external_running_ != nullptr && external_running_->load()) {
        MSG msg{};
        const BOOL ret = GetMessage(&msg, nullptr, 0, 0);
        if (ret == 0 || ret == -1) {
            break;
        }
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    if (foreground_hook_ != nullptr) {
        UnhookWinEvent(foreground_hook_);
        foreground_hook_ = nullptr;
    }
    if (namechange_hook_ != nullptr) {
        UnhookWinEvent(namechange_hook_);
        namechange_hook_ = nullptr;
    }
    if (audio_timer_id_ != 0U) {
        KillTimer(nullptr, audio_timer_id_);
        audio_timer_id_ = 0U;
    }

    g_active_context_provider = nullptr;

    if (co_init_success) {
        CoUninitialize();
    }
#else
    core::ContextSnapshot snapshot{};
    snapshot.header.sequence_number = sequence_number_++;
    snapshot.header.timestamp = std::chrono::steady_clock::now();
    snapshot.app_id = "unknown";
    snapshot.window_title = "Unknown";
    snapshot.context_mode = core::ContextMode::Desktop;
    snapshot.is_audio_playing = false;
    publisher_.publish(snapshot);
#endif

    running_.store(false);
    external_running_ = nullptr;
    thread_id_ = 0U;
}

void ContextProvider::stop() {
    running_.store(false);
    if (external_running_ != nullptr) {
        external_running_->store(false);
    }
#ifdef _WIN32
    if (thread_id_ != 0U) {
        PostThreadMessage(thread_id_, WM_QUIT, 0, 0);
    }
#endif
}

#ifdef _WIN32
void CALLBACK ContextProvider::win_event_callback(
    HWINEVENTHOOK,
    DWORD event,
    HWND hwnd,
    LONG,
    LONG,
    DWORD,
    DWORD) {
    if (g_active_context_provider == nullptr) {
        return;
    }
    g_active_context_provider->handle_win_event(event, hwnd);
}

void CALLBACK ContextProvider::timer_callback(HWND, UINT, UINT_PTR timer_id, DWORD) {
    if (g_active_context_provider == nullptr) {
        return;
    }
    g_active_context_provider->handle_audio_timer(timer_id);
}

void ContextProvider::handle_win_event(const DWORD event, HWND hwnd) {
    if (!running_.load() || external_running_ == nullptr || !external_running_->load()) {
        return;
    }

    const HWND foreground = GetForegroundWindow();
    if (foreground == nullptr) {
        return;
    }

    if (event == EVENT_OBJECT_NAMECHANGE && hwnd != foreground) {
        return;
    }

    publish_context_snapshot(foreground, current_audio_state_.load());
}

void ContextProvider::handle_audio_timer(const UINT_PTR timer_id) {
    if (timer_id != audio_timer_id_ || !running_.load() || external_running_ == nullptr || !external_running_->load()) {
        return;
    }

    const bool next_audio_state = check_is_audio_playing();
    publish_context_snapshot(GetForegroundWindow(), next_audio_state);
}

void ContextProvider::publish_context_snapshot(HWND hwnd, const bool audio_state) {
    const HWND foreground = hwnd != nullptr ? hwnd : GetForegroundWindow();
    const std::string process_name = get_foreground_process_name();
    const std::string window_title = get_foreground_window_title();

    core::ContextMode mode = process_name.empty()
        ? core::ContextMode::Desktop
        : registry_.classify_by_process(process_name);

    std::string domain;
    if (mode == core::ContextMode::Browser && foreground != nullptr) {
        const auto uia_started = std::chrono::steady_clock::now();
        domain = uia::get_browser_domain(foreground);
        const auto uia_elapsed =
            std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - uia_started);
        if (uia_elapsed.count() > 10) {
            core::log_line(
                "[Context][Warning] UIA lookup took ",
                uia_elapsed.count(),
                "ms for process=",
                process_name);
        }

        const core::ContextMode domain_mode = registry_.classify_by_domain(domain);
        if (domain_mode != core::ContextMode::Unknown) {
            mode = domain_mode;
        }
    }

    std::optional<core::ContextSnapshot> snapshot_to_publish;
    std::string log_domain = domain.empty() ? "<none>" : domain;
    {
        std::lock_guard<std::mutex> lock(state_mutex_);
        current_audio_state_.store(audio_state);

        const auto now = std::chrono::steady_clock::now();
        if (audio_state) {
            persistent_media_app_ = process_name;
            last_audio_time_ = now;
        }

        if (process_name == persistent_media_app_ &&
            std::chrono::duration_cast<std::chrono::minutes>(now - last_audio_time_).count() < 15) {
            if (mode == core::ContextMode::Browser || mode == core::ContextMode::Desktop) {
                mode = core::ContextMode::Media;
            }
        }

        if (mode != previous_mode_ || audio_state != previous_audio_) {
            core::ContextSnapshot snapshot{};
            snapshot.header.sequence_number = sequence_number_++;
            snapshot.header.timestamp = std::chrono::steady_clock::now();
            snapshot.app_id = process_name;
            snapshot.window_title = window_title;
            snapshot.context_mode = mode;
            snapshot.is_audio_playing = audio_state;
            snapshot_to_publish = snapshot;

            previous_mode_ = mode;
            previous_audio_ = audio_state;
        }
    }

    if (snapshot_to_publish.has_value() && publisher_.publish(*snapshot_to_publish)) {
        core::log_line(
            "[ContextEvent] process=",
            process_name.empty() ? "<unknown>" : process_name,
            " domain=",
            log_domain,
            " mode=",
            core::to_string(mode),
            audio_state ? " [Audio Active]" : "");
    }
}
#endif

}  // namespace spider::context
