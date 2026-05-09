#include "voice/voice_source.hpp"

#include <array>
#include <chrono>
#include <thread>

#include "core/logging.hpp"

namespace spider::voice {

namespace {

constexpr std::array<const char*, 9> kVoiceCommands{
    "switch to voice mode",
    "open app",
    "scroll up",
    "volume up",
    "navigate left",
    "zoom in",
    "switch to hand mode",
    "select",
    "scroll down"
};

}  // namespace

VoiceSource::VoiceSource(bus::Publisher<core::VoiceEvent> publisher)
    : publisher_(std::move(publisher)) {}

void VoiceSource::run(std::atomic<bool>& running) {
    std::uint64_t sequence_number = 1U;
    std::size_t index = 0U;

    while (running.load()) {
        core::VoiceEvent event{};
        event.header.sequence_number = sequence_number;
        event.header.timestamp = std::chrono::steady_clock::now();
        event.text = kVoiceCommands[index];
        event.confidence = 0.92F;

        if (publisher_.publish(event)) {
            core::log_line("[Voice] \"", event.text, "\"");
        }

        ++sequence_number;
        index = (index + 1U) % kVoiceCommands.size();

        for (int step = 0; step < 30 && running.load(); ++step) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
}

}  // namespace spider::voice
