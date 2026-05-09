#include "perception/gesture_extractor.hpp"

#include "core/logging.hpp"

namespace spider::perception {

namespace {

const char* gesture_for_frame(const std::uint64_t frame_id) {
    switch (frame_id % 12U) {
    case 0U:
    case 1U:
    case 2U:
        return "MOVE_HAND";
    case 3U:
    case 4U:
    case 5U:
        return "OPEN_PALM";
    case 6U:
    case 7U:
    case 8U:
        return "SWIPE_UP";
    default:
        return "PINCH";
    }
}

float confidence_for_frame(const std::uint64_t frame_id) {
    return 0.80F + static_cast<float>(frame_id % 10U) * 0.01F;
}

}  // namespace

core::GestureEvent GestureExtractor::extract(const HandState& hand) const {
    core::GestureEvent gesture{};
    gesture.header = hand.header;
    gesture.label = gesture_for_frame(hand.frame_id);
    gesture.confidence = confidence_for_frame(hand.frame_id);
    gesture.hand_id = hand.hand_id;

    spider::core::log_line("[Gesture] ", gesture.label);
    return gesture;
}

}  // namespace spider::perception
