#pragma once

#include <atomic>

#include "bus/event_bus.hpp"
#include "core/voice_event.hpp"

namespace spider::voice {

class VoiceSource final {
public:
    explicit VoiceSource(bus::Publisher<core::VoiceEvent> publisher);

    void run(std::atomic<bool>& running);

private:
    bus::Publisher<core::VoiceEvent> publisher_;
};

}  // namespace spider::voice
