#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <mutex>
#include <string>

#include "bus/event_bus.hpp"
#include "context/context_registry.hpp"
#include "core/context_snapshot.hpp"

#ifdef _WIN32
#include <windows.h>
#endif

namespace spider::context {

class ContextProvider final {
public:
    ContextProvider(bus::Publisher<core::ContextSnapshot> publisher, const std::string& config_path);

    void run(std::atomic<bool>& running);
    void stop();

private:
#ifdef _WIN32
    static void CALLBACK win_event_callback(
        HWINEVENTHOOK hook,
        DWORD event,
        HWND hwnd,
        LONG id_object,
        LONG id_child,
        DWORD event_thread,
        DWORD event_time);
    static void CALLBACK timer_callback(HWND hwnd, UINT message, UINT_PTR timer_id, DWORD time);

    void handle_win_event(DWORD event, HWND hwnd);
    void handle_audio_timer(UINT_PTR timer_id);
    void publish_context_snapshot(HWND hwnd, bool audio_state);
#endif

    bus::Publisher<core::ContextSnapshot> publisher_;
    ContextRegistry registry_;
    std::atomic<bool> running_{false};
    std::atomic<bool>* external_running_{nullptr};
    std::uint32_t thread_id_{0U};
    std::uint64_t sequence_number_{1U};
    core::ContextMode previous_mode_{core::ContextMode::Unknown};
    bool previous_audio_{false};
    std::atomic<bool> current_audio_state_{false};
    std::string persistent_media_app_;
    std::chrono::steady_clock::time_point last_audio_time_{std::chrono::steady_clock::now()};
    std::mutex state_mutex_;
#ifdef _WIN32
    HWINEVENTHOOK foreground_hook_{nullptr};
    HWINEVENTHOOK namechange_hook_{nullptr};
    UINT_PTR audio_timer_id_{0U};
#endif
};

}  // namespace spider::context
