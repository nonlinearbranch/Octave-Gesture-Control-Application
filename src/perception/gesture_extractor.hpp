#pragma once

#include "core/gesture_event.hpp"
#include "perception/hand_state.hpp"

namespace spider::perception {

class GestureExtractor final {
public:
    core::GestureEvent extract(const HandState& hand) const;
};

}  // namespace spider::perception
