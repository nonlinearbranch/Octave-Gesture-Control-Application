#pragma once

#include <string>

#include "core/event_header.hpp"

namespace spider::core {

struct VoiceEvent {
    EventHeader header{};
    std::string text{};
    float confidence{0.0F};
};

}  // namespace spider::core
