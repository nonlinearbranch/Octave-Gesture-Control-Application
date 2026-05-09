#include "voice/voice_intent_mapper.hpp"

#include <optional>
#include <string>

namespace spider::voice {

std::optional<core::IntentEvent> VoiceIntentMapper::map(const core::VoiceEvent& voice) const {
    const auto maybe_intent = map_text_to_intent(voice.text);
    if (!maybe_intent.has_value()) {
        return std::nullopt;
    }

    core::IntentEvent intent{};
    intent.header = voice.header;
    intent.intent = *maybe_intent;
    intent.confidence = voice.confidence;
    intent.hand_id = 0;
    intent.source = core::InputSource::Voice;
    intent.source_label = voice.text;
    intent.semantic_label = semantic_label_for_text(voice.text);
    intent.value = 0.1F;

    return intent;
}

std::optional<core::IntentKind> VoiceIntentMapper::map_text_to_intent(const std::string& text) {
    if (text == "scroll up") {
        return core::IntentKind::Scroll;
    }
    if (text == "scroll down") {
        return core::IntentKind::Scroll;
    }
    if (text == "volume up") {
        return core::IntentKind::Adjust;
    }
    if (text == "volume down") {
        return core::IntentKind::Adjust;
    }
    if (text == "zoom in") {
        return core::IntentKind::Adjust;
    }
    if (text == "zoom out") {
        return core::IntentKind::Adjust;
    }
    if (text == "select") {
        return core::IntentKind::Select;
    }
    if (text == "open app") {
        return core::IntentKind::Select;
    }
    if (text == "navigate left") {
        return core::IntentKind::Select;
    }
    if (text == "navigate right") {
        return core::IntentKind::Select;
    }
    if (text == "stop") {
        return core::IntentKind::Select;
    }
    return std::nullopt;
}

std::string VoiceIntentMapper::semantic_label_for_text(const std::string& text) {
    if (text == "scroll up") {
        return "ScrollUp";
    }
    if (text == "scroll down") {
        return "ScrollDown";
    }
    if (text == "volume up") {
        return "VolumeUp";
    }
    if (text == "volume down") {
        return "VolumeDown";
    }
    if (text == "zoom in") {
        return "ZoomIn";
    }
    if (text == "zoom out") {
        return "ZoomOut";
    }
    if (text == "select") {
        return "Click";
    }
    if (text == "open app") {
        return "OpenBrowser";
    }
    if (text == "navigate left") {
        return "GoBack";
    }
    if (text == "navigate right") {
        return "GoForward";
    }
    if (text == "stop") {
        return "Escape";
    }
    return {};
}

}  // namespace spider::voice
