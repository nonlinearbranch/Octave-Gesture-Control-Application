#pragma once

#include "core/event_header.hpp"

namespace spider::core {

enum class ContinuousDomain {
    Cursor,
    Scroll,
    Adjust,
    ScrollSpeed,
    Volume,
    Zoom,
    Brightness
};

inline const char* to_string(const ContinuousDomain domain) {
    switch (domain) {
    case ContinuousDomain::Cursor:
        return "Cursor";
    case ContinuousDomain::Scroll:
        return "Scroll";
    case ContinuousDomain::Adjust:
        return "Adjust";
    case ContinuousDomain::ScrollSpeed:
        return "ScrollSpeed";
    case ContinuousDomain::Volume:
        return "Volume";
    case ContinuousDomain::Zoom:
        return "Zoom";
    case ContinuousDomain::Brightness:
        return "Brightness";
    default:
        return "Unknown";
    }
}

struct ContinuousActionStart {
    EventHeader header{};
    std::uint64_t interaction_id{0};
    int hand_id{0};
    ContinuousDomain domain{ContinuousDomain::Adjust};
};

struct ContinuousActionUpdate {
    EventHeader header{};
    std::uint64_t interaction_id{0};
    int hand_id{0};
    ContinuousDomain domain{ContinuousDomain::Adjust};
    float delta{0.0F};
};

struct ContinuousActionStop {
    EventHeader header{};
    std::uint64_t interaction_id{0};
    int hand_id{0};
    ContinuousDomain domain{ContinuousDomain::Adjust};
};

}  // namespace spider::core
