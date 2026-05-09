#pragma once

#include <string>

#include "core/event_header.hpp"

namespace spider::core {

enum class InputSource {
    Gesture,
    Voice
};

enum class IntentKind {
    Select,
    Scroll,
    Adjust
};

struct IntentEvent {
    EventHeader header{};
    IntentKind intent{IntentKind::Select};
    float confidence{0.0F};
    int hand_id{0};
    InputSource source{InputSource::Gesture};
    std::string source_label{};
    std::string semantic_label{};
    float value{0.0F};
};

inline const char* to_string(const IntentKind intent) {
    switch (intent) {
    case IntentKind::Select:
        return "Select";
    case IntentKind::Scroll:
        return "Scroll";
    case IntentKind::Adjust:
        return "Adjust";
    default:
        return "Unknown";
    }
}

}  // namespace spider::core
