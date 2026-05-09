#include "perception/perception_pipeline.hpp"

#include <chrono>
#include <thread>

namespace spider::perception {

PerceptionPipeline::PerceptionPipeline(
    bus::Subscriber<Frame> frame_subscriber,
    bus::Publisher<core::GestureEvent> gesture_publisher,
    std::shared_ptr<runtime::ModeManager> mode_manager)
    : frame_subscriber_(std::move(frame_subscriber)),
      gesture_publisher_(std::move(gesture_publisher)),
      mode_manager_(std::move(mode_manager)) {}

void PerceptionPipeline::run(std::atomic<bool>& running) {
    Frame frame{};

    while (running.load() && frame_subscriber_.wait_and_pop(frame)) {
        if (mode_manager_ &&
            mode_manager_->getMode() == runtime::InteractionMode::VOICE) {
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
            continue;
        }

        const HandState hand = hand_tracker_.track(frame);
        const core::GestureEvent gesture = gesture_extractor_.extract(hand);
        gesture_publisher_.publish(gesture);
    }
}

}  // namespace spider::perception
