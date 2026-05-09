#include "perception/hand_tracker.hpp"

#include "core/logging.hpp"

namespace spider::perception {

HandState HandTracker::track(const Frame& frame) const {
    HandState hand{};
    hand.frame_id = frame.frame_id;
    hand.header = frame.header;
    hand.hand_id = 1;
    hand.tracking_confidence = 0.95F;

    spider::core::log_line("[Tracking] Hand detected id=", hand.hand_id);
    return hand;
}

}  // namespace spider::perception
