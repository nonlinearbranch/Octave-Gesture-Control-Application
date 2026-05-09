#pragma once

#include <chrono>
#include <cstdint>

namespace spider::core {

struct EventHeader {
    std::uint64_t sequence_number{0};
    std::chrono::steady_clock::time_point timestamp{};
};

}  // namespace spider::core
