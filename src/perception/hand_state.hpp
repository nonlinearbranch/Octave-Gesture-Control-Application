#pragma once

#include <cstdint>

#include "core/event_header.hpp"

namespace spider::perception {

struct HandState {
    std::uint64_t frame_id{0};
    spider::core::EventHeader header{};
    int hand_id{0};
    float tracking_confidence{0.0F};
};

}  // namespace spider::perception
