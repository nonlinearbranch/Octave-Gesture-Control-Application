#pragma once

#include <atomic>
#include <filesystem>
#include <memory>
#include <thread>

#include "action/action_executor.hpp"
#include "bus/event_bus.hpp"
#include "core/continuous_action.hpp"
#include "core/context_snapshot.hpp"
#include "core/gesture_event.hpp"
#include "core/intent_event.hpp"
#include "context/context_provider.hpp"
#include "decision/decision_engine.hpp"
#include "intent/gesture_mapping_registry.hpp"
#include "intent/intent_normalizer.hpp"
#include "core/voice_event.hpp"
#include "heuristics/HeuristicsTracker.hpp"
#include "ipc/engine_command_server.hpp"
#include "ipc/python_ml_service_client.hpp"
#include "ipc/python_service_process.hpp"
#include "runtime/mode_manager.hpp"

namespace spider::runtime {

class PipelineDemo final {
public:
    PipelineDemo();
    ~PipelineDemo();

    void start();
    void stop();

private:
    std::filesystem::path project_root_;
    std::atomic<bool> running_{false};
    bus::EventBus<core::GestureEvent> gesture_bus_;
    bus::EventBus<core::VoiceEvent> voice_bus_;
    bus::EventBus<core::IntentEvent> intent_bus_;
    bus::EventBus<core::ContextSnapshot> context_bus_;
    bus::EventBus<core::ContinuousActionStart> continuous_start_bus_;
    bus::EventBus<core::ContinuousActionUpdate> continuous_update_bus_;
    bus::EventBus<core::ContinuousActionStop> continuous_stop_bus_;
    std::shared_ptr<ModeManager> mode_manager_;
    std::shared_ptr<intent::GestureMappingRegistry> mapping_registry_;
    std::shared_ptr<spider::heuristics::HeuristicsTracker> heuristics_tracker_;
    ipc::PythonServiceProcess python_service_process_;
    std::shared_ptr<ipc::PythonMlServiceClient> ml_service_client_;
    ipc::EngineCommandServer command_server_;
    intent::IntentNormalizer intent_normalizer_;
    context::ContextProvider context_provider_;
    decision::DecisionEngine decision_engine_;
    action::ActionExecutor action_executor_;
    std::thread ml_service_thread_;
    std::thread command_server_thread_;
    std::thread intent_thread_;
    std::thread context_thread_;
    std::thread decision_thread_;
    std::thread action_thread_;
};

}  // namespace spider::runtime
