#pragma once

#include <string>

#include "core/event_header.hpp"

namespace spider::core {

enum class ContextMode {
    Unknown,
    Browser,
    Media,
    Editor,
    Desktop
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
    default:
        return "Unknown";
    }
}

struct ContextSnapshot {
    EventHeader header{};
    std::string app_id{};
    std::string window_title{};
    ContextMode context_mode{ContextMode::Unknown};
};

}  // namespace spider::core
