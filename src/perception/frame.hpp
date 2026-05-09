#pragma once

#include <cstdint>
#include <vector>

#include "core/event_header.hpp"

namespace spider::perception {

struct Frame {
    std::uint64_t frame_id{0};
    spider::core::EventHeader header{};
    std::vector<std::uint8_t> pixel_buffer{};
};

}  // namespace spider::perception
