#pragma once

#include <atomic>
#include <memory>

#include "bus/event_bus.hpp"
#include "perception/frame.hpp"
#include "runtime/mode_manager.hpp"

namespace spider::perception {

class FrameSource final {
public:
    FrameSource(
        bus::Publisher<Frame> publisher,
        std::shared_ptr<runtime::ModeManager> mode_manager);

    void run(std::atomic<bool>& running);

private:
    bus::Publisher<Frame> publisher_;
    std::shared_ptr<runtime::ModeManager> mode_manager_;
};

}  // namespace spider::perception
