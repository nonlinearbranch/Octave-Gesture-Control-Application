#pragma once

#include <atomic>
#include <memory>

#include "bus/event_bus.hpp"
#include "core/gesture_event.hpp"
#include "perception/frame.hpp"
#include "perception/gesture_extractor.hpp"
#include "perception/hand_tracker.hpp"
#include "runtime/mode_manager.hpp"

namespace spider::perception {

class PerceptionPipeline final {
public:
    PerceptionPipeline(
        bus::Subscriber<Frame> frame_subscriber,
        bus::Publisher<core::GestureEvent> gesture_publisher,
        std::shared_ptr<runtime::ModeManager> mode_manager);

    void run(std::atomic<bool>& running);

private:
    bus::Subscriber<Frame> frame_subscriber_;
    bus::Publisher<core::GestureEvent> gesture_publisher_;
    std::shared_ptr<runtime::ModeManager> mode_manager_;
    HandTracker hand_tracker_;
    GestureExtractor gesture_extractor_;
};

}  // namespace spider::perception
