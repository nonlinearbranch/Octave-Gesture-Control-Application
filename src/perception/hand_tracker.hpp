#pragma once

#include "perception/frame.hpp"
#include "perception/hand_state.hpp"

namespace spider::perception {

class HandTracker final {
public:
    HandState track(const Frame& frame) const;
};

}  // namespace spider::perception
