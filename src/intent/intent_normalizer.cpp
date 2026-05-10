#include "intent/intent_normalizer.hpp"

#include <chrono>
#include <string>
#include <thread>

#include "core/logging.hpp"

namespace spider::intent {

IntentNormalizer::IntentNormalizer(
    bus::Subscriber<core::GestureEvent> gesture_subscriber,
    bus::Subscriber<core::VoiceEvent> voice_subscriber,
    bus::Publisher<core::IntentEvent> intent_publisher,
    std::shared_ptr<runtime::ModeManager> mode_manager,
    std::shared_ptr<GestureMappingRegistry> mapping_registry,
    std::shared_ptr<ipc::PythonMlServiceClient> ml_client)
    : gesture_subscriber_(std::move(gesture_subscriber)),
      voice_subscriber_(std::move(voice_subscriber)),
      intent_publisher_(std::move(intent_publisher)),
      mode_manager_(std::move(mode_manager)),
      mapping_registry_(std::move(mapping_registry)),
      ml_client_(std::move(ml_client)) {}

void IntentNormalizer::run(std::atomic<bool>& running) {
    core::GestureEvent gesture{};
    core::VoiceEvent voice{};

    while (running.load()) {
        bool processed = false;

        if (voice_subscriber_.try_pop(voice)) {

            if (mode_manager_ && mode_manager_->getMode() != runtime::InteractionMode::VOICE) {
                processed = true;
                continue;
            }

            if (mapping_registry_) {
                const auto custom_action = mapping_registry_->resolve_voice_action(voice.text);
                if (custom_action.has_value()) {
                    core::IntentEvent intent{};
                    intent.header = voice.header;
                    intent.intent = core::IntentKind::Select;
                    intent.confidence = voice.confidence;
                    intent.hand_id = 0;
                    intent.source = core::InputSource::Voice;
                    intent.source_label = voice.text;
                    intent.semantic_label = *custom_action;
                    intent.value = 0.0F;
                    if (intent_publisher_.publish(intent)) {
                        core::log_line("[VoiceIntent] ", intent.semantic_label);
                    }
                    processed = true;
                    continue;
                }
            }

            const auto intent = voice_mapper_.map(voice);
            if (intent.has_value() && intent_publisher_.publish(*intent)) {
                core::log_line("[VoiceIntent] ", intent->semantic_label.empty() ? core::to_string(intent->intent) : intent->semantic_label);
            }
            processed = true;
            continue;
        }

        if (gesture_subscriber_.try_pop(gesture)) {
            if (mode_manager_ && mode_manager_->getMode() != runtime::InteractionMode::HAND) {
                processed = true;
                continue;
            }

            const auto binding =
                mapping_registry_ ? mapping_registry_->resolve_gesture(gesture.label) : std::nullopt;
            if (!binding.has_value()) {
                processed = true;
                continue;
            }

            core::IntentEvent intent{};
            intent.header = gesture.header;
            intent.intent = binding->intent;
            intent.confidence = gesture.confidence;
            intent.hand_id = gesture.hand_id;
            intent.source = core::InputSource::Gesture;
            intent.source_label = gesture.label;
            intent.semantic_label = binding->action;
            intent.value = gesture.value;
            intent.index_x = gesture.index_x;
            intent.index_y = gesture.index_y;
            intent.thumb_x = gesture.thumb_x;
            intent.thumb_y = gesture.thumb_y;

            if (intent_publisher_.publish(intent)) {
                core::log_line("[Intent] ", core::to_string(intent.intent));
            }
            processed = true;
        }

        if (!processed) {
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }
}

}  // namespace spider::intent
