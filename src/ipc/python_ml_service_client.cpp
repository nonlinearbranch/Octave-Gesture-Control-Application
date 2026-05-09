#include "ipc/python_ml_service_client.hpp"
#include "heuristics/HeuristicsTracker.hpp"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <sstream>
#include <string>
#include <thread>

#include "core/logging.hpp"

namespace spider::ipc {

PythonMlServiceClient::PythonMlServiceClient(
    bus::Publisher<core::GestureEvent> gesture_publisher,
    bus::Publisher<core::VoiceEvent> voice_publisher,
    std::shared_ptr<spider::heuristics::HeuristicsTracker> heuristics_tracker,
    std::string host,
    const std::uint16_t port,
    std::shared_ptr<intent::GestureMappingRegistry> mapping_registry)
    : gesture_publisher_(std::move(gesture_publisher)),
      voice_publisher_(std::move(voice_publisher)),
      heuristics_tracker_(std::move(heuristics_tracker)),
      host_(std::move(host)),
      port_(port),
      mapping_registry_(std::move(mapping_registry)) {}

PythonMlServiceClient::~PythonMlServiceClient() {
    disconnect();
}

bool PythonMlServiceClient::connect() {
#ifndef _WIN32
    return false;
#else
    WSADATA wsa_data{};
    if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0) {
        return false;
    }
    wsa_initialized_ = true;

    socket_ = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (socket_ == INVALID_SOCKET) {
        disconnect();
        return false;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(port_);
    inet_pton(AF_INET, host_.c_str(), &address.sin_addr);

    if (::connect(socket_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == SOCKET_ERROR) {
        disconnect();
        return false;
    }

    return true;
#endif
}

void PythonMlServiceClient::disconnect() {
#ifdef _WIN32
    if (socket_ != INVALID_SOCKET) {
        closesocket(socket_);
        socket_ = INVALID_SOCKET;
    }
    if (wsa_initialized_) {
        WSACleanup();
        wsa_initialized_ = false;
    }
#endif
}

void PythonMlServiceClient::run(std::atomic<bool>& running) {
#ifndef _WIN32
    return;
#else
    while (running.load()) {
        // Connect phase — retry until connected or stopped
        while (running.load() && socket_ == INVALID_SOCKET) {
            if (connect()) {
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(250));
        }

        if (socket_ == INVALID_SOCKET) {
            break;
        }

        core::log_line("[IPC] Connected to Python ML service");

        // Recv phase — process messages until disconnect
        std::string buffer;
        char recv_buffer[4096];

        while (running.load()) {
            const int received = recv(socket_, recv_buffer, sizeof(recv_buffer), 0);
            if (received <= 0) {
                break;
            }

            buffer.append(recv_buffer, recv_buffer + received);
            std::size_t newline = 0U;
            while ((newline = buffer.find('\n')) != std::string::npos) {
                const std::string line = buffer.substr(0, newline);
                buffer.erase(0, newline + 1U);
                if (!line.empty()) {
                    handle_line(line);
                }
            }
        }

        // Disconnect phase — clean up and retry
        core::log_line("[IPC] Disconnected from Python ML service, reconnecting...");
        disconnect();
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
#endif
}

bool PythonMlServiceClient::send_start_recording(
    const std::string& label,
    const std::string& action,
    const std::string& gesture_type) {
    return send_json(
        "{\"command\":\"START_RECORDING\",\"label\":\"" + escape_json(label) +
        "\",\"action\":\"" + escape_json(action) +
        "\",\"gesture_type\":\"" + escape_json(gesture_type) + "\"}\n");
}

bool PythonMlServiceClient::send_stop_recording() {
    return send_json("{\"command\":\"STOP_RECORDING\"}\n");
}

bool PythonMlServiceClient::send_train_model() {
    return send_json("{\"command\":\"TRAIN_MODEL\"}\n");
}

bool PythonMlServiceClient::send_train_model_and_wait(
    const std::chrono::milliseconds timeout,
    std::string& status,
    std::string& error) {
    {
        std::lock_guard<std::mutex> lock(training_mutex_);
        training_pending_ = true;
        training_status_.clear();
        training_error_.clear();
    }

    if (!send_train_model()) {
        std::lock_guard<std::mutex> lock(training_mutex_);
        training_pending_ = false;
        status = "send_failed";
        error = "ML service is not connected";
        return false;
    }

    std::unique_lock<std::mutex> lock(training_mutex_);
    const bool completed = training_cv_.wait_for(lock, timeout, [this] {
        return !training_pending_;
    });
    if (!completed) {
        training_pending_ = false;
        status = "timeout";
        error = "Timed out waiting for training to finish";
        return false;
    }

    status = training_status_;
    error = training_error_;
    return status == "trained";
}

void PythonMlServiceClient::get_recording_status(
    bool& active,
    int& sample_count,
    int& target_samples,
    std::string& label) {
    std::lock_guard<std::mutex> lock(recording_mutex_);
    active = recording_active_;
    sample_count = recording_sample_count_;
    target_samples = recording_target_samples_;
    label = recording_label_;
}

bool PythonMlServiceClient::send_delete_gesture(const std::string& label) {
    return send_json("{\"command\":\"DELETE_GESTURE\",\"label\":\"" + escape_json(label) + "\"}\n");
}

bool PythonMlServiceClient::send_voice_text(const std::string& text) {
    return send_json("{\"command\":\"VOICE_TEXT\",\"text\":\"" + escape_json(text) + "\"}\n");
}

bool PythonMlServiceClient::send_mode(const std::string& mode) {
    return send_json("{\"command\":\"SET_MODE\",\"mode\":\"" + escape_json(mode) + "\"}\n");
}

bool PythonMlServiceClient::send_shutdown() {
    return send_json("{\"command\":\"SHUTDOWN\"}\n");
}

bool PythonMlServiceClient::send_settings(
    const int camera_index,
    const int voice_input_index,
    const float hand_min_detection_confidence,
    const float voice_phrase_cooldown_sec) {
    std::ostringstream out;
    out << "{\"command\":\"SET_SETTINGS\",\"settings\":{"
        << "\"camera_index\":" << camera_index << ","
        << "\"voice_input_index\":" << voice_input_index << ","
        << "\"hand_min_detection_confidence\":" << hand_min_detection_confidence << ","
        << "\"voice_phrase_cooldown_sec\":" << voice_phrase_cooldown_sec
        << "}}\n";
    return send_json(out.str());
}

bool PythonMlServiceClient::send_json(const std::string& json) {
#ifndef _WIN32
    return false;
#else
    if (socket_ == INVALID_SOCKET) {
        return false;
    }

    std::lock_guard<std::mutex> lock(send_mutex_);
    return send(socket_, json.c_str(), static_cast<int>(json.size()), 0) != SOCKET_ERROR;
#endif
}

bool PythonMlServiceClient::handle_line(const std::string& line) {
    const std::string type = extract_string(line, "type");
    const std::string event_type = extract_string(line, "event");
    const std::string message_type = !type.empty() ? type : event_type;

    if (message_type == "gesture") {
        const std::string label = extract_string(line, "label");
        const std::string mode = extract_string(line, "mode");
        const std::string action = extract_string(line, "action");
        const float index_x = extract_nested_float(line, "index_tip", "x", NAN);
        const float index_y = extract_nested_float(line, "index_tip", "y", NAN);
        const float thumb_x = extract_nested_float(line, "thumb_tip", "x", NAN);
        const float thumb_y = extract_nested_float(line, "thumb_tip", "y", NAN);
        const float confidence = extract_float(line, "confidence", 0.0F);

        if (action.find("Mode:") == 0) {
            // Continuous action -> feed to heuristics tracker, bypass discrete publisher
            if (heuristics_tracker_) {
                heuristics_tracker_->process_payload(label, action, index_x, index_y, thumb_x, thumb_y);
            }
            core::log_line("[IPC] Continuous Mode ", action, " confidence=", confidence);
            return true;
        }

        // Discrete action
        if (heuristics_tracker_) {
            heuristics_tracker_->enter_idle();
        }

        core::GestureEvent event{};
        event.header.sequence_number = sequence_number_++;
        event.header.timestamp = std::chrono::steady_clock::now();
        event.label = label;
        event.confidence = confidence;
        event.hand_id = 1;
        gesture_publisher_.publish(event);
        core::log_line("[IPC] Gesture ", event.label, " ", event.confidence,
                       " action=", action, " mode=", mode.empty() ? "unknown" : mode);
        return true;
    }

    if (message_type == "voice") {
        core::VoiceEvent event{};
        event.header.sequence_number = sequence_number_++;
        event.header.timestamp = std::chrono::steady_clock::now();
        
        std::string text = extract_string(line, "text");
        
        // Trim trailing whitespace
        text.erase(std::find_if(text.rbegin(), text.rend(), [](unsigned char ch) {
            return !std::isspace(ch);
        }).base(), text.end());
        
        // Trim leading whitespace
        text.erase(text.begin(), std::find_if(text.begin(), text.end(), [](unsigned char ch) {
            return !std::isspace(ch);
        }));
        
        // Convert to lowercase
        std::transform(text.begin(), text.end(), text.begin(), [](unsigned char c) { 
            return std::tolower(c); 
        });

        event.text = text;
        event.confidence = extract_float(line, "confidence", 0.0F);
        voice_publisher_.publish(event);
        core::log_line("[IPC] Voice '", event.text, "'");
        return true;
    }

    if (type == "status") {
        const std::string message = extract_string(line, "message");
        const std::string error = extract_string(line, "error");
        const std::string state = extract_string(line, "state");

        {
            std::lock_guard<std::mutex> lock(recording_mutex_);
            recording_active_ = state == "recording";
            recording_label_ = extract_string(line, "active_label");
            recording_sample_count_ = static_cast<int>(extract_float(line, "sample_count", recording_sample_count_));
            recording_target_samples_ = static_cast<int>(extract_float(line, "target_samples", recording_target_samples_));
            if (recording_target_samples_ <= 0) {
                recording_target_samples_ = 320;
            }
        }
        
        // extract_string might accidentally grab "cv2_error=" if "error" is empty
        // Let's ensure we only log error if it actually looks like a real error
        if (!error.empty() && error.find("cv2_error=") == std::string::npos) {
            core::log_line("[IPC] Status ", message, " error=", error);
        } else {
            core::log_line("[IPC] Status ", message);
        }
        return true;
    }

    if (type == "training") {
        const std::string status = extract_string(line, "status");
        core::log_line("[IPC] Training ", status);

        if (status == "trained" && mapping_registry_) {
            const auto labels = extract_string_array(line, "labels");
            for (const auto& label : labels) {
                if (!mapping_registry_->resolve_gesture(label).has_value()) {
                    mapping_registry_->register_label(label);
                    core::log_line("[IPC] Auto-registered new gesture: ", label);
                }
            }
        }
        if (status == "trained" || status == "failed" || status == "busy") {
            std::lock_guard<std::mutex> lock(training_mutex_);
            training_status_ = status;
            training_error_ = extract_string(line, "error");
            training_pending_ = false;
            training_cv_.notify_all();
        }
        return true;
    }

    if (type == "training_progress") {
        core::log_line("[IPC] TrainingProgress ", extract_float(line, "progress", 0.0F));
        return true;
    }

    if (type == "mode") {
        core::log_line("[IPC] ServiceMode ", extract_string(line, "mode"));
        return true;
    }

    core::log_line("[IPC] ", line);
    return false;
}

std::string PythonMlServiceClient::extract_string(
    const std::string& json,
    const std::string& key) {
    const std::string token = "\"" + key + "\"";
    const std::size_t start = json.find(token);
    if (start == std::string::npos) {
        return {};
    }
    std::size_t value_start = json.find(':', start + token.size());
    if (value_start == std::string::npos) {
        return {};
    }
    ++value_start;
    while (value_start < json.size() && std::isspace(static_cast<unsigned char>(json[value_start]))) {
        ++value_start;
    }
    if (value_start >= json.size() || json[value_start] != '"') {
        return {};
    }
    ++value_start;
    const std::size_t value_end = json.find('"', value_start);
    if (value_end == std::string::npos) {
        return {};
    }
    return json.substr(value_start, value_end - value_start);
}

float PythonMlServiceClient::extract_float(
    const std::string& json,
    const std::string& key,
    const float fallback) {
    const std::string token = "\"" + key + "\"";
    const std::size_t start = json.find(token);
    if (start == std::string::npos) {
        return fallback;
    }
    std::size_t value_start = json.find(':', start + token.size());
    if (value_start == std::string::npos) {
        return fallback;
    }
    ++value_start;
    while (value_start < json.size() && std::isspace(static_cast<unsigned char>(json[value_start]))) {
        ++value_start;
    }
    const std::size_t value_end = json.find_first_of(",}", value_start);
    const std::string raw = json.substr(value_start, value_end - value_start);
    try {
        return std::stof(raw);
    } catch (...) {
        return fallback;
    }
}

float PythonMlServiceClient::extract_nested_float(
    const std::string& json,
    const std::string& object_key,
    const std::string& field_key,
    const float fallback) {
    const std::string object_token = "\"" + object_key + "\"";
    const std::size_t object_start = json.find(object_token);
    if (object_start == std::string::npos) {
        return fallback;
    }
    const std::size_t brace_start = json.find('{', object_start + object_token.size());
    if (brace_start == std::string::npos) {
        return fallback;
    }
    const std::size_t field_start = json.find("\"" + field_key + "\"", brace_start);
    if (field_start == std::string::npos) {
        return fallback;
    }
    return extract_float(json.substr(field_start), field_key, fallback);
}

std::string PythonMlServiceClient::escape_json(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size());
    for (const char ch : value) {
        switch (ch) {
        case '\\':
            escaped += "\\\\";
            break;
        case '"':
            escaped += "\\\"";
            break;
        case '\n':
            escaped += "\\n";
            break;
        case '\r':
            escaped += "\\r";
            break;
        case '\t':
            escaped += "\\t";
            break;
        default:
            escaped += ch;
            break;
        }
    }
    return escaped;
}

std::vector<std::string> PythonMlServiceClient::extract_string_array(
    const std::string& json,
    const std::string& key) {
    std::vector<std::string> result;
    const std::string token = "\"" + key + "\"";
    const std::size_t start = json.find(token);
    if (start == std::string::npos) {
        return result;
    }
    const std::size_t bracket = json.find('[', start + token.size());
    if (bracket == std::string::npos) {
        return result;
    }
    const std::size_t end_bracket = json.find(']', bracket);
    if (end_bracket == std::string::npos) {
        return result;
    }
    std::size_t pos = bracket + 1;
    while (pos < end_bracket) {
        const std::size_t quote_start = json.find('"', pos);
        if (quote_start == std::string::npos || quote_start >= end_bracket) {
            break;
        }
        const std::size_t quote_end = json.find('"', quote_start + 1);
        if (quote_end == std::string::npos || quote_end >= end_bracket) {
            break;
        }
        result.push_back(json.substr(quote_start + 1, quote_end - quote_start - 1));
        pos = quote_end + 1;
    }
    return result;
}

}  // namespace spider::ipc
