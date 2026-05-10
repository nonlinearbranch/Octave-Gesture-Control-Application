#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <memory>
#include <unordered_map>
#include <unordered_set>

#include "bus/event_bus.hpp"
#include "core/continuous_action.hpp"
#include "core/context_snapshot.hpp"
#include "core/intent_event.hpp"
#include "runtime/mode_manager.hpp"

namespace spider::decision {

class DecisionEngine final {
public:
    struct ActiveInteraction {
        std::uint64_t interaction_id{0};
        int hand_id{0};
        core::ContinuousDomain domain{core::ContinuousDomain::Adjust};
        bool is_active{false};
        std::chrono::steady_clock::time_point last_update{};
    };

    DecisionEngine(
        bus::Subscriber<core::IntentEvent> subscriber,
        bus::Subscriber<core::ContextSnapshot> context_subscriber,
        bus::Publisher<core::ContinuousActionStart> start_publisher,
        bus::Publisher<core::ContinuousActionUpdate> update_publisher,
        bus::Publisher<core::ContinuousActionStop> stop_publisher,
        std::shared_ptr<runtime::ModeManager> mode_manager);

    void run(std::atomic<bool>& running);

private:
    static const char* action_message(core::IntentKind intent);
    static const char* adjusting_message(core::ContinuousDomain domain);
    static const char* voice_action_message(const core::IntentEvent& intent);
    std::string resolve_discrete_action(const core::IntentEvent& intent) const;
    core::ContinuousDomain resolve_continuous_domain(const core::IntentEvent& intent) const;
    core::ContinuousDomain domain_for_context() const;
    void handle_mode_transition(runtime::InteractionMode new_mode);
    void handle_context_update(const core::ContextSnapshot& context);
    void handle_intent_event(const core::IntentEvent& intent);
    bool has_active_interaction(int hand_id) const;
    void cleanup_active_interaction(int hand_id, const core::EventHeader& header);
    void emit_start_for_hand(
        int hand_id,
        const core::EventHeader& header,
        core::ContinuousDomain domain);
    void emit_update_for_hand(
        int hand_id,
        const core::EventHeader& header,
        const core::IntentEvent& intent,
        core::ContinuousDomain domain);
    void emit_stop_for_hand(
        int hand_id,
        const core::EventHeader& header);
    void transition_active_interaction(
        int hand_id,
        const core::EventHeader& header,
        core::ContinuousDomain new_domain);
    bool is_continuous_adjust(const core::IntentEvent& intent) const;

    bus::Subscriber<core::IntentEvent> subscriber_;
    bus::Subscriber<core::ContextSnapshot> context_subscriber_;
    bus::Publisher<core::ContinuousActionStart> start_publisher_;
    bus::Publisher<core::ContinuousActionUpdate> update_publisher_;
    bus::Publisher<core::ContinuousActionStop> stop_publisher_;
    std::shared_ptr<runtime::ModeManager> mode_manager_;
    std::unordered_map<int, ActiveInteraction> active_interactions_;
    std::unordered_set<std::uint64_t> active_interaction_ids_;
    core::ContextSnapshot latest_context_{};
    std::uint64_t next_interaction_id_{1};
    runtime::InteractionMode current_mode_{runtime::InteractionMode::HAND};
    std::chrono::milliseconds interaction_idle_timeout_{500};
};

}  // namespace spider::decision
