#include "perception/frame_source.hpp"

#include <chrono>
#include <thread>

#include "core/logging.hpp"

namespace spider::perception {

FrameSource::FrameSource(
    bus::Publisher<Frame> publisher,
    std::shared_ptr<runtime::ModeManager> mode_manager)
    : publisher_(std::move(publisher)),
      mode_manager_(std::move(mode_manager)) {}

void FrameSource::run(std::atomic<bool>& running) {
    std::uint64_t frame_id = 1U;

    while (running.load()) {
        Frame frame{};
        frame.frame_id = frame_id;
        frame.header.sequence_number = frame_id;
        frame.header.timestamp = std::chrono::steady_clock::now();
        frame.pixel_buffer = {0U, 1U, 2U, 3U};

        if (publisher_.publish(frame)) {
            spider::core::log_line("[Frame] Captured id=", frame.frame_id);
        }

        ++frame_id;
        const auto mode = mode_manager_
                              ? mode_manager_->getMode()
                              : runtime::InteractionMode::HAND;
        if (mode == runtime::InteractionMode::VOICE) {
            std::this_thread::sleep_for(std::chrono::milliseconds(250));
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(33));
        }
    }
}

}  // namespace spider::perception
