#pragma once

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <string>

#include "bus/event_bus.hpp"
#include "core/gesture_event.hpp"
#include "core/voice_event.hpp"
#include "intent/gesture_mapping_registry.hpp"

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#endif

namespace spider::heuristics {
class HeuristicsTracker;
}

namespace spider::ipc {

class PythonMlServiceClient final {
public:
    PythonMlServiceClient(
        bus::Publisher<core::GestureEvent> gesture_publisher,
        bus::Publisher<core::VoiceEvent> voice_publisher,
        std::shared_ptr<spider::heuristics::HeuristicsTracker> heuristics_tracker,
        std::string host = "127.0.0.1",
        std::uint16_t port = 50555,
        std::shared_ptr<intent::GestureMappingRegistry> mapping_registry = nullptr);

    ~PythonMlServiceClient();

    bool connect();
    void disconnect();
    void run(std::atomic<bool>& running);

    bool send_start_recording(
        const std::string& label,
        const std::string& action = "Click",
        const std::string& gesture_type = "static");
    bool send_stop_recording();
    bool send_train_model();
    bool send_train_model_and_wait(
        std::chrono::milliseconds timeout,
        std::string& status,
        std::string& error);
    void get_recording_status(
        bool& active,
        int& sample_count,
        int& target_samples,
        std::string& label);
    bool send_delete_gesture(const std::string& label);
    bool send_voice_text(const std::string& text);
    bool send_mode(const std::string& mode);
    bool send_shutdown();
    bool send_settings(
        int camera_index,
        int voice_input_index,
        float hand_min_detection_confidence,
        float voice_phrase_cooldown_sec);

private:
    bool send_json(const std::string& json);
    bool handle_line(const std::string& line);
    static std::string extract_string(const std::string& json, const std::string& key);
    static float extract_float(const std::string& json, const std::string& key, float fallback);
    static float extract_nested_float(
        const std::string& json,
        const std::string& object_key,
        const std::string& field_key,
        float fallback);
    static std::string escape_json(const std::string& value);
    static std::vector<std::string> extract_string_array(const std::string& json, const std::string& key);

    bus::Publisher<core::GestureEvent> gesture_publisher_;
    bus::Publisher<core::VoiceEvent> voice_publisher_;
    std::string host_;
    std::uint16_t port_;
#ifdef _WIN32
    SOCKET socket_{INVALID_SOCKET};
    bool wsa_initialized_{false};
#endif
    std::uint64_t sequence_number_{1};
    std::mutex send_mutex_;
    std::mutex training_mutex_;
    std::condition_variable training_cv_;
    bool training_pending_{false};
    std::string training_status_;
    std::string training_error_;
    std::mutex recording_mutex_;
    bool recording_active_{false};
    int recording_sample_count_{0};
    int recording_target_samples_{320};
    std::string recording_label_;
    std::shared_ptr<intent::GestureMappingRegistry> mapping_registry_;
    std::shared_ptr<spider::heuristics::HeuristicsTracker> heuristics_tracker_;
};

}  // namespace spider::ipc
