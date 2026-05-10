#pragma once

#include <string>

#include "core/event_header.hpp"

namespace spider::core {

struct GestureEvent {
    EventHeader header{};
    std::string label{};
    float confidence{0.0F};
    int hand_id{0};
    float value{0.0F};
    float index_x{0.0F};
    float index_y{0.0F};
    float thumb_x{0.0F};
    float thumb_y{0.0F};
};

}  // namespace spider::core
