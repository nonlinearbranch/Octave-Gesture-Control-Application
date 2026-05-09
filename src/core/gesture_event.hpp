#pragma once

#include <string>

#include "core/event_header.hpp"

namespace spider::core {

struct GestureEvent {
    EventHeader header{};
    std::string label{};
    float confidence{0.0F};
    int hand_id{0};
};

}  // namespace spider::core
