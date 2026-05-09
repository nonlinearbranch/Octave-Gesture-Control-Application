#include "ipc/engine_command_server.hpp"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <sstream>

#include "core/logging.hpp"

namespace spider::ipc {

EngineCommandServer::EngineCommandServer(
    std::shared_ptr<PythonMlServiceClient> ml_client,
    std::shared_ptr<intent::GestureMappingRegistry> mapping_registry,
    std::shared_ptr<runtime::ModeManager> mode_manager,
    bus::Publisher<core::VoiceEvent> voice_publisher,
    const std::uint16_t port)
    : ml_client_(std::move(ml_client)),
      mapping_registry_(std::move(mapping_registry)),
      mode_manager_(std::move(mode_manager)),
      voice_publisher_(std::move(voice_publisher)),
      port_(port) {}

void EngineCommandServer::run(std::atomic<bool>& running) {
#ifndef _WIN32
    return;
#else
    WSADATA wsa_data{};
    if (WSAStartup(MAKEWORD(2, 2), &wsa_data) != 0) {
        return;
    }

    SOCKET server = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (server == INVALID_SOCKET) {
        WSACleanup();
        return;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_port = htons(port_);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    bind(server, reinterpret_cast<sockaddr*>(&address), sizeof(address));
    listen(server, 4);

    while (running.load()) {
        fd_set read_set;
        FD_ZERO(&read_set);
        FD_SET(server, &read_set);
        timeval timeout{};
        timeout.tv_sec = 0;
        timeout.tv_usec = 200000;
        const int select_result = select(0, &read_set, nullptr, nullptr, &timeout);
        if (select_result <= 0) {
            continue;
        }

        SOCKET client = accept(server, nullptr, nullptr);
        if (client == INVALID_SOCKET) {
            continue;
        }

        std::string buffer;
        char recv_buffer[2048];
        while (running.load()) {
            const int received = recv(client, recv_buffer, sizeof(recv_buffer), 0);
            if (received <= 0) {
                break;
            }

            buffer.append(recv_buffer, recv_buffer + received);
            std::size_t newline = buffer.find('\n');
            while (newline != std::string::npos) {
                const std::string line = buffer.substr(0, newline);
                buffer.erase(0, newline + 1);
                if (!line.empty()) {
                    const std::string response = handle_command(line);
                    send(client, response.c_str(), static_cast<int>(response.size()), 0);
                }
                newline = buffer.find('\n');
            }
        }
        if (!buffer.empty()) {
            const std::string response = handle_command(buffer);
            send(client, response.c_str(), static_cast<int>(response.size()), 0);
        }
        closesocket(client);
    }

    closesocket(server);
    WSACleanup();
#endif
}

std::string EngineCommandServer::handle_command(const std::string& line) {
    const std::string command = extract_string(line, "command");
    if (command == "start_recording") {
        const std::string label = extract_string(line, "label");
        const std::string action = extract_string(line, "action");
        const std::string gesture_type = extract_string(line, "gesture_type");
        const bool ok = ml_client_ && ml_client_->send_start_recording(
            label,
            action.empty() ? "Click" : action,
            gesture_type.empty() ? "static" : gesture_type);
        return std::string("{\"ok\":") + (ok ? "true" : "false") + "}\n";
    }

    if (command == "stop_recording") {
        const bool ok = ml_client_ && ml_client_->send_stop_recording();
        return std::string("{\"ok\":") + (ok ? "true" : "false") + "}\n";
    }

    if (command == "train_model") {
        std::string status;
        std::string error;
        const bool ok = ml_client_ &&
            ml_client_->send_train_model_and_wait(
                std::chrono::seconds(180),
                status,
                error);
        return std::string("{\"ok\":") + (ok ? "true" : "false") +
               ",\"status\":\"" + escape_json(status) +
               "\",\"error\":\"" + escape_json(error) + "\"}\n";
    }

    if (command == "recording_status") {
        bool active = false;
        int sample_count = 0;
        int target_samples = 320;
        std::string label;
        if (ml_client_) {
            ml_client_->get_recording_status(active, sample_count, target_samples, label);
        }
        std::ostringstream out;
        out << "{\"ok\":true,"
            << "\"active\":" << (active ? "true" : "false") << ','
            << "\"sample_count\":" << sample_count << ','
            << "\"target_samples\":" << target_samples << ','
            << "\"label\":\"" << escape_json(label) << "\"}\n";
        return out.str();
    }

    if (command == "update_settings") {
        const int camera_index =
            static_cast<int>(extract_number(line, "camera_index", 0.0));
        const int voice_input_index =
            static_cast<int>(extract_number(line, "voice_input_index", -1.0));
        const float hand_min_detection_confidence =
            static_cast<float>(extract_number(line, "hand_min_detection_confidence", 0.5));
        const float voice_phrase_cooldown_sec =
            static_cast<float>(extract_number(line, "voice_phrase_cooldown_sec", 0.5));

        const bool ok = ml_client_ &&
            ml_client_->send_settings(
                camera_index,
                voice_input_index,
                hand_min_detection_confidence,
                voice_phrase_cooldown_sec);
        return std::string("{\"ok\":") + (ok ? "true" : "false") + "}\n";
    }

    if (command == "delete_gesture") {
        const std::string label = extract_string(line, "label");
        const std::string type = extract_string(line, "type");
        if (mapping_registry_ && type == "voice") {
            mapping_registry_->delete_voice_action(label);
        } else if (mapping_registry_) {
            mapping_registry_->delete_label(label);
        }
        const bool ok = ml_client_ && ml_client_->send_delete_gesture(label);
        return std::string("{\"ok\":") + (ok ? "true" : "false") + "}\n";
    }

    if (command == "list_gestures") {
        std::ostringstream out;
        out << "{\"ok\":true,\"gestures\":[";
        if (mapping_registry_) {
            const auto labels = mapping_registry_->list_labels();
            for (std::size_t i = 0; i < labels.size(); ++i) {
                if (i > 0) {
                    out << ',';
                }
                out << '"' << escape_json(labels[i]) << '"';
            }
        }
        out << "],\"mapping\":{\"disabled_static\":[";
        if (mapping_registry_) {
            const auto disabled = mapping_registry_->list_disabled_static();
            for (std::size_t index = 0; index < disabled.size(); ++index) {
                if (index > 0) {
                    out << ',';
                }
                out << '"' << escape_json(disabled[index]) << '"';
            }
        }
        out << "],\"static_actions\":{";
        if (mapping_registry_) {
            const auto actions = mapping_registry_->list_static_actions();
            bool first = true;
            for (const auto& entry : actions) {
                if (!first) {
                    out << ',';
                }
                first = false;
                out << '"' << escape_json(entry.first) << "\":\"" << escape_json(entry.second) << '"';
            }
        }
        out << "},\"voice_actions\":{";
        if (mapping_registry_) {
            const auto actions = mapping_registry_->list_voice_actions();
            bool first = true;
            for (const auto& entry : actions) {
                if (!first) {
                    out << ',';
                }
                first = false;
                out << '"' << escape_json(entry.first) << "\":\"" << escape_json(entry.second) << '"';
            }
        }
        out << "}}}\n";
        return out.str();
    }

    if (command == "set_disabled_static") {
        const std::string labels = extract_string(line, "labels");
        std::vector<std::string> parsed;
        std::stringstream stream(labels);
        std::string label;
        while (std::getline(stream, label, '|')) {
            if (!label.empty()) {
                parsed.push_back(label);
            }
        }
        if (mapping_registry_) {
            mapping_registry_->set_disabled_static(parsed);
        }
        return "{\"ok\":true}\n";
    }

    if (command == "upsert_gesture") {
        const std::string old_name = extract_string(line, "old_name");
        const std::string new_name = extract_string(line, "new_name");
        const std::string action = extract_string(line, "action");
        const bool ok = mapping_registry_ && mapping_registry_->update_gesture(old_name, new_name, action);
        return std::string("{\"ok\":") + (ok ? "true" : "false") + "}\n";
    }

    if (command == "upsert_voice_action") {
        const std::string phrase = extract_string(line, "phrase");
        const std::string action = extract_string(line, "action");
        if (mapping_registry_) {
            mapping_registry_->upsert_voice_action(phrase, action);
        }
        return "{\"ok\":true}\n";
    }

    if (command == "set_mode") {
        const std::string mode = extract_string(line, "mode");
        if (mode_manager_) {
            mode_manager_->setMode(mode == "VOICE" ? runtime::InteractionMode::VOICE : runtime::InteractionMode::HAND);
        }
        if (ml_client_) {
            ml_client_->send_mode(mode == "VOICE" ? "VOICE" : "HAND");
        }
        return std::string("{\"ok\":true,\"mode\":\"") +
               (mode_manager_ ? runtime::to_string(mode_manager_->getMode()) : "HAND") +
               "\"}\n";
    }

    if (command == "get_mode") {
        return std::string("{\"ok\":true,\"mode\":\"") +
               (mode_manager_ ? runtime::to_string(mode_manager_->getMode()) : "HAND") +
               "\"}\n";
    }

    if (command == "voice_text") {
        const std::string text = extract_string(line, "text");

        // Intercept mode-switch commands — sync both sides directly
        if (text == "switch to voice mode" || text == "switch to hand mode") {
            const bool is_voice = (text == "switch to voice mode");
            if (mode_manager_) {
                mode_manager_->setMode(is_voice
                    ? runtime::InteractionMode::VOICE
                    : runtime::InteractionMode::HAND);
            }
            if (ml_client_) {
                ml_client_->send_mode(is_voice ? "VOICE" : "HAND");
            }
            return std::string("{\"ok\":true,\"mode\":\"") +
                   (is_voice ? "VOICE" : "HAND") + "\"}\n";
        }

        core::VoiceEvent event{};
        event.header.sequence_number = voice_sequence_++;
        event.header.timestamp = std::chrono::steady_clock::now();
        event.text = text;
        event.confidence = 1.0F;
        const bool ok = voice_publisher_.publish(event);
        return std::string("{\"ok\":") + (ok ? "true" : "false") + "}\n";
    }

    return "{\"ok\":false,\"error\":\"unknown_command\"}\n";
}

std::string EngineCommandServer::extract_string(const std::string& json, const std::string& key) {
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

double EngineCommandServer::extract_number(
    const std::string& json,
    const std::string& key,
    const double fallback) {
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
        return std::stod(raw);
    } catch (...) {
        return fallback;
    }
}

std::string EngineCommandServer::escape_json(const std::string& value) {
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

}  // namespace spider::ipc
