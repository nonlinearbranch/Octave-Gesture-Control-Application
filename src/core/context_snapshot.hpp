#pragma once

#include <string>

#include "core/event_header.hpp"

namespace spider::core {

enum class ContextMode {
    Unknown,
    Browser,
    Media,
    Editor,
    Desktop,
    Presentation,
    Conferencing,
    Gaming,
    Design
};

inline const char* to_string(const ContextMode mode) {
    switch (mode) {
    case ContextMode::Unknown:
        return "Unknown";
    case ContextMode::Browser:
        return "Browser";
    case ContextMode::Media:
        return "Media";
    case ContextMode::Editor:
        return "Editor";
    case ContextMode::Desktop:
        return "Desktop";
    case ContextMode::Presentation:
        return "Presentation";
    case ContextMode::Conferencing:
        return "Conferencing";
    case ContextMode::Gaming:
        return "Gaming";
    case ContextMode::Design:
        return "Design";
    default:
        return "Unknown";
    }
}

struct ContextSnapshot {
    EventHeader header{};
    std::string app_id{};
    std::string window_title{};
    ContextMode context_mode{ContextMode::Unknown};
    bool is_audio_playing{false};
};

}  // namespace spider::core
