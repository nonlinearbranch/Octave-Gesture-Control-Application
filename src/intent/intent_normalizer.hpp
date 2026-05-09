#pragma once

#include <atomic>
#include <memory>

#include "bus/event_bus.hpp"
#include "core/gesture_event.hpp"
#include "core/intent_event.hpp"
#include "core/voice_event.hpp"
#include "intent/gesture_mapping_registry.hpp"
#include "ipc/python_ml_service_client.hpp"
#include "runtime/mode_manager.hpp"
#include "voice/voice_intent_mapper.hpp"

namespace spider::intent {

class IntentNormalizer final {
public:
    IntentNormalizer(
        bus::Subscriber<core::GestureEvent> gesture_subscriber,
        bus::Subscriber<core::VoiceEvent> voice_subscriber,
        bus::Publisher<core::IntentEvent> intent_publisher,
        std::shared_ptr<runtime::ModeManager> mode_manager,
        std::shared_ptr<GestureMappingRegistry> mapping_registry,
        std::shared_ptr<ipc::PythonMlServiceClient> ml_client = nullptr);

    void run(std::atomic<bool>& running);

private:
    bus::Subscriber<core::GestureEvent> gesture_subscriber_;
    bus::Subscriber<core::VoiceEvent> voice_subscriber_;
    bus::Publisher<core::IntentEvent> intent_publisher_;
    std::shared_ptr<runtime::ModeManager> mode_manager_;
    std::shared_ptr<GestureMappingRegistry> mapping_registry_;
    std::shared_ptr<ipc::PythonMlServiceClient> ml_client_;
    spider::voice::VoiceIntentMapper voice_mapper_;
};

}  // namespace spider::intent
