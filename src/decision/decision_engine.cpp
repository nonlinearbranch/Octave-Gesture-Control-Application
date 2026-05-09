#include "decision/decision_engine.hpp"

#include <chrono>
#include <thread>

#include "action/desktop_actions.hpp"
#include "core/logging.hpp"

namespace spider::decision {

DecisionEngine::DecisionEngine(
    bus::Subscriber<core::IntentEvent> subscriber,
    bus::Subscriber<core::ContextSnapshot> context_subscriber,
    bus::Publisher<core::ContinuousActionStart> start_publisher,
    bus::Publisher<core::ContinuousActionUpdate> update_publisher,
    bus::Publisher<core::ContinuousActionStop> stop_publisher,
    std::shared_ptr<runtime::ModeManager> mode_manager)
    : subscriber_(std::move(subscriber)),
      context_subscriber_(std::move(context_subscriber)),
      start_publisher_(std::move(start_publisher)),
      update_publisher_(std::move(update_publisher)),
      stop_publisher_(std::move(stop_publisher)),
      mode_manager_(std::move(mode_manager)) {
    latest_context_.context_mode = core::ContextMode::Unknown;
    if (mode_manager_) {
        current_mode_ = mode_manager_->getMode();
    }
}

void DecisionEngine::run(std::atomic<bool>& running) {
    core::IntentEvent intent{};
    core::ContextSnapshot context{};

    while (running.load()) {
        bool processed = false;

        if (mode_manager_) {
            const auto next_mode = mode_manager_->getMode();
            if (next_mode != current_mode_) {
                handle_mode_transition(next_mode);
                current_mode_ = next_mode;
                processed = true;
            }
        }

        while (context_subscriber_.try_pop(context)) {
            handle_context_update(context);
            processed = true;
        }

        if (!subscriber_.try_pop(intent)) {
            if (!processed) {
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
            continue;
        }

        processed = true;
        handle_intent_event(intent);
    }
}

const char* DecisionEngine::action_message(const core::IntentKind intent) {
    switch (intent) {
    case core::IntentKind::Scroll:
        return "Scrolling...";
    case core::IntentKind::Select:
        return "Selecting...";
    case core::IntentKind::Adjust:
        return "Adjusting...";
    default:
        return "No action.";
    }
}

const char* DecisionEngine::adjusting_message(const core::ContinuousDomain domain) {
    switch (domain) {
    case core::ContinuousDomain::ScrollSpeed:
        return "Adjusting Scroll Speed";
    case core::ContinuousDomain::Volume:
        return "Adjusting Volume";
    case core::ContinuousDomain::Zoom:
        return "Adjusting Zoom";
    case core::ContinuousDomain::Brightness:
        return "Adjusting Brightness";
    default:
        return "Adjusting...";
    }
}

const char* DecisionEngine::voice_action_message(const core::IntentEvent& intent) {
    if (!intent.semantic_label.empty()) {
        return action::desktop_actions::describe_action(intent.semantic_label);
    }
    return action_message(intent.intent);
}

namespace {

std::string fallback_action_for_intent(const spider::core::IntentEvent& intent) {
    if (!intent.semantic_label.empty()) {
        return intent.semantic_label;
    }
    if (intent.source == spider::core::InputSource::Gesture) {
        if (intent.source_label == "OPEN_PALM") {
            return "Click";
        }
        if (intent.source_label == "SWIPE_UP") {
            return "ScrollUp";
        }
    }
    if (intent.source == spider::core::InputSource::Voice) {
        if (intent.intent == spider::core::IntentKind::Select) {
            return "Click";
        }
        if (intent.intent == spider::core::IntentKind::Scroll) {
            return "ScrollUp";
        }
    }
    return {};
}

}  // namespace

core::ContinuousDomain DecisionEngine::domain_for_context() const {
    switch (latest_context_.context_mode) {
    case core::ContextMode::Browser:
        return core::ContinuousDomain::ScrollSpeed;
    case core::ContextMode::Media:
        return core::ContinuousDomain::Volume;
    case core::ContextMode::Editor:
        return core::ContinuousDomain::Zoom;
    case core::ContextMode::Desktop:
        return core::ContinuousDomain::Brightness;
    default:
        return core::ContinuousDomain::Adjust;
    }
}

void DecisionEngine::handle_mode_transition(const runtime::InteractionMode new_mode) {
    for (auto& entry : active_interactions_) {
        if (!entry.second.is_active) {
            continue;
        }

        cleanup_active_interaction(entry.first, latest_context_.header);
    }

    active_interaction_ids_.clear();
    core::log_line("[Mode] Switched to ", runtime::to_string(new_mode));
}

void DecisionEngine::handle_context_update(const core::ContextSnapshot& context) {
    latest_context_ = context;
    if (current_mode_ != runtime::InteractionMode::HAND) {
        return;
    }

    const core::ContinuousDomain new_domain = domain_for_context();

    for (auto& entry : active_interactions_) {
        const int hand_id = entry.first;
        const auto& interaction = entry.second;
        if (!interaction.is_active || interaction.domain == new_domain) {
            continue;
        }

        transition_active_interaction(hand_id, context.header, new_domain);
    }
}

void DecisionEngine::handle_intent_event(const core::IntentEvent& intent) {
    if (current_mode_ == runtime::InteractionMode::HAND &&
        intent.source != core::InputSource::Gesture) {
        return;
    }
    if (current_mode_ == runtime::InteractionMode::VOICE &&
        intent.source != core::InputSource::Voice) {
        return;
    }

    if (current_mode_ == runtime::InteractionMode::HAND && is_continuous_adjust(intent)) {
        const core::ContinuousDomain domain = domain_for_context();
        if (!has_active_interaction(intent.hand_id)) {
            emit_start_for_hand(intent.hand_id, intent.header, domain);
        } else {
            emit_update_for_hand(intent.hand_id, intent.header, intent.value);
        }
        core::log_line("[Decision] ", adjusting_message(domain));
        return;
    }

    if (current_mode_ == runtime::InteractionMode::HAND) {
        emit_stop_for_hand(intent.hand_id, intent.header);
        const std::string action_id = fallback_action_for_intent(intent);
        action::desktop_actions::execute_discrete_action(action_id);
        core::log_line(
            "[Decision] ",
            action_id.empty() ? action_message(intent.intent)
                              : action::desktop_actions::describe_action(action_id));
        return;
    }

    const std::string action_id = fallback_action_for_intent(intent);
    action::desktop_actions::execute_discrete_action(action_id);
    core::log_line("[Decision] ", voice_action_message(intent));
}

bool DecisionEngine::has_active_interaction(const int hand_id) const {
    const auto it = active_interactions_.find(hand_id);
    return it != active_interactions_.end() && it->second.is_active;
}

void DecisionEngine::cleanup_active_interaction(
    const int hand_id,
    const core::EventHeader& header) {
    auto it = active_interactions_.find(hand_id);
    if (it == active_interactions_.end() || !it->second.is_active) {
        return;
    }

    core::log_line(
        "[ModeTransition] Cleaning active interaction ",
        it->second.interaction_id);
    emit_stop_for_hand(hand_id, header);
}

void DecisionEngine::emit_start_for_hand(
    const int hand_id,
    const core::EventHeader& header,
    const core::ContinuousDomain domain) {
    auto& interaction = active_interactions_[hand_id];
    if (interaction.is_active) {
        return;
    }

    interaction.interaction_id = next_interaction_id_++;
    interaction.hand_id = hand_id;
    interaction.domain = domain;
    interaction.is_active = true;
    active_interaction_ids_.clear();
    active_interaction_ids_.insert(interaction.interaction_id);

    core::ContinuousActionStart start{};
    start.header = header;
    start.interaction_id = interaction.interaction_id;
    start.hand_id = hand_id;
    start.domain = domain;
    start_publisher_.publish(start);
}

void DecisionEngine::emit_update_for_hand(
    const int hand_id,
    const core::EventHeader& header,
    const float delta) {
    auto it = active_interactions_.find(hand_id);
    if (it == active_interactions_.end() || !it->second.is_active) {
        return;
    }
    if (active_interaction_ids_.find(it->second.interaction_id) == active_interaction_ids_.end()) {
        return;
    }

    core::ContinuousActionUpdate update{};
    update.header = header;
    update.interaction_id = it->second.interaction_id;
    update.hand_id = hand_id;
    update.domain = it->second.domain;
    update.delta = delta;
    update_publisher_.publish(update);
}

void DecisionEngine::emit_stop_for_hand(
    const int hand_id,
    const core::EventHeader& header) {
    auto it = active_interactions_.find(hand_id);
    if (it == active_interactions_.end() || !it->second.is_active) {
        return;
    }

    const core::ContinuousDomain previous_domain = it->second.domain;
    core::ContinuousActionStop stop{};
    stop.header = header;
    stop.interaction_id = it->second.interaction_id;
    stop.hand_id = hand_id;
    stop.domain = previous_domain;
    stop_publisher_.publish(stop);
    active_interaction_ids_.erase(it->second.interaction_id);

    it->second = ActiveInteraction{};
    it->second.hand_id = hand_id;
}

void DecisionEngine::transition_active_interaction(
    const int hand_id,
    const core::EventHeader& header,
    const core::ContinuousDomain new_domain) {
    auto it = active_interactions_.find(hand_id);
    if (it == active_interactions_.end() || !it->second.is_active) {
        return;
    }

    const core::ContinuousDomain old_domain = it->second.domain;
    if (old_domain == new_domain) {
        return;
    }

    emit_stop_for_hand(hand_id, header);
    core::log_line(
        "[Transition] ContextSwitch Old=",
        core::to_string(old_domain),
        " New=",
        core::to_string(new_domain));
    emit_start_for_hand(hand_id, header, new_domain);
    core::log_line("[Decision] ", adjusting_message(new_domain));
}

bool DecisionEngine::is_continuous_adjust(const core::IntentEvent& intent) const {
    return intent.source == core::InputSource::Gesture &&
           intent.intent == core::IntentKind::Adjust;
}

}  // namespace spider::decision
