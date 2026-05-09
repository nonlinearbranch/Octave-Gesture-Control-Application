#pragma once

#include <optional>
#include <string>

#include "core/intent_event.hpp"
#include "core/voice_event.hpp"

namespace spider::voice {

class VoiceIntentMapper final {
public:
    std::optional<core::IntentEvent> map(const core::VoiceEvent& voice) const;

private:
    static std::optional<core::IntentKind> map_text_to_intent(const std::string& text);
    static std::string semantic_label_for_text(const std::string& text);
};

}  // namespace spider::voice
