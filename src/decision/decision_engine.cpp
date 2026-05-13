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
        const auto now = std::chrono::steady_clock::now();

        if (mode_manager_) {
            const auto next_mode = mode_manager_->getMode();
            if (next_mode != current_mode_) {
                handle_mode_transition(next_mode);
                current_mode_ = next_mode;
                processed = true;
            }
        }

        for (auto& entry : active_interactions_) {
            if (!entry.second.is_active) {
                continue;
            }
            if (now - entry.second.last_update > interaction_idle_timeout_) {
                emit_stop_for_hand(entry.first, latest_context_.header);
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
    case core::ContinuousDomain::Timeline:
        return "Adjusting Timeline";
    case core::ContinuousDomain::Cursor:
        return "Moving Cursor";
    case core::ContinuousDomain::Scroll:
        return "Scrolling";
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

core::ContinuousDomain DecisionEngine::domain_for_context() const {
    switch (latest_context_.context_mode) {
    case core::ContextMode::Browser:
        return core::ContinuousDomain::ScrollSpeed;
    case core::ContextMode::Media:
        return core::ContinuousDomain::Volume;
    case core::ContextMode::Editor:
    case core::ContextMode::Design:
        return core::ContinuousDomain::Zoom;
    case core::ContextMode::Desktop:
    case core::ContextMode::Gaming:
        return core::ContinuousDomain::Brightness;
    case core::ContextMode::Presentation:
        return core::ContinuousDomain::ScrollSpeed;
    case core::ContextMode::Conferencing:
        return core::ContinuousDomain::Volume;
    default:
        // ContinuousDomain::Adjust has no implementation in
        // apply_continuous_update (falls through to default: break).
        // Volume is the most universally useful fallback when the
        // foreground process cannot be classified.
        return core::ContinuousDomain::Volume;
    }
}

std::string DecisionEngine::resolve_discrete_action(const core::IntentEvent& intent) const {
    if (intent.semantic_label == "Context: Swipe Left") {
        switch (latest_context_.context_mode) {
        case core::ContextMode::Browser: return "SwitchTabPrev";
        case core::ContextMode::Media: return "PrevTrack";
        case core::ContextMode::Editor:
        case core::ContextMode::Design: return "Undo";
        case core::ContextMode::Presentation: return "PrevSlide";
        default: return "GoBack";
        }
    }
    if (intent.semantic_label == "Context: Swipe Right") {
        switch (latest_context_.context_mode) {
        case core::ContextMode::Browser: return "SwitchTab";
        case core::ContextMode::Media: return "NextTrack";
        case core::ContextMode::Editor:
        case core::ContextMode::Design: return "Redo";
        case core::ContextMode::Presentation: return "NextSlide";
        default: return "GoForward";
        }
    }
    if (intent.semantic_label == "Context: Dial Clockwise") {
        switch (latest_context_.context_mode) {
        case core::ContextMode::Media: return "VolumeUp";
        case core::ContextMode::Editor:
        case core::ContextMode::Design: return "BrushSizeIncrease";
        case core::ContextMode::Desktop: return "SwitchTab";
        case core::ContextMode::Gaming: return "WeaponNext";
        default: return "VolumeUp";
        }
    }
    if (intent.semantic_label == "Context: Dial Counter Clockwise") {
        switch (latest_context_.context_mode) {
        case core::ContextMode::Media: return "VolumeDown";
        case core::ContextMode::Editor:
        case core::ContextMode::Design: return "BrushSizeDecrease";
        case core::ContextMode::Desktop: return "SwitchWindow";
        case core::ContextMode::Gaming: return "WeaponPrev";
        default: return "VolumeDown";
        }
    }
    if (intent.semantic_label == "Context: Fist") {
        switch (latest_context_.context_mode) {
        case core::ContextMode::Browser: return "ToggleFullscreenVideo";
        case core::ContextMode::Desktop: return "ToggleStartMenu";
        case core::ContextMode::Conferencing: return "MuteToggle";
        case core::ContextMode::Media: return "PlayPause";
        default: return "PlayPause";
        }
    }
    return intent.semantic_label;
}

core::ContinuousDomain DecisionEngine::resolve_continuous_domain(const core::IntentEvent& intent) const {
    if (intent.semantic_label == "Mode: Cursor Control" ||
        intent.semantic_label == "Mode: Context Drag") {
        return core::ContinuousDomain::Cursor;
    }

    if (intent.semantic_label == "Mode: Context Vertical") {
        switch (latest_context_.context_mode) {
        case core::ContextMode::Media:
            return core::ContinuousDomain::Timeline;
        case core::ContextMode::Editor:
        case core::ContextMode::Design:
            return core::ContinuousDomain::Zoom;
        case core::ContextMode::Browser:
        case core::ContextMode::Presentation:
            return core::ContinuousDomain::Scroll;
        default:
            return core::ContinuousDomain::Scroll;
        }
    }

    if (intent.semantic_label == "Mode: Context Slider") {
        return domain_for_context();
    }

    return domain_for_context();
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

    for (auto& entry : active_interactions_) {
        if (!entry.second.is_active) {
            continue;
        }
        const core::ContinuousDomain new_domain = domain_for_context();
        if (entry.second.domain != new_domain &&
            entry.second.domain != core::ContinuousDomain::Cursor) {
            transition_active_interaction(entry.first, context.header, new_domain);
        }
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
        const core::ContinuousDomain domain = resolve_continuous_domain(intent);
        if (!has_active_interaction(intent.hand_id)) {
            emit_start_for_hand(intent.hand_id, intent.header, domain);
        }
        emit_update_for_hand(intent.hand_id, intent.header, intent, domain);
        core::log_line("[Decision] ", adjusting_message(domain));
        return;
    }

    if (current_mode_ == runtime::InteractionMode::HAND) {
        emit_stop_for_hand(intent.hand_id, intent.header);
        const std::string action_id = resolve_discrete_action(intent);
        if (!action_id.empty() && action_id != "None") {
            action::desktop_actions::execute_discrete_action(action_id);
        }
        core::log_line(
            "[Decision] ",
            action_id.empty() ? action_message(intent.intent)
                              : action::desktop_actions::describe_action(action_id));
        return;
    }

    const std::string action_id = resolve_discrete_action(intent);
    if (!action_id.empty() && action_id != "None") {
        action::desktop_actions::execute_discrete_action(action_id);
    }
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

    core::log_line("[ModeTransition] Cleaning active interaction ", it->second.interaction_id);
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
    interaction.last_update = std::chrono::steady_clock::now();
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
    const core::IntentEvent& intent,
    const core::ContinuousDomain domain) {
    auto it = active_interactions_.find(hand_id);
    if (it == active_interactions_.end() || !it->second.is_active) {
        return;
    }
    if (it->second.domain != domain) {
        transition_active_interaction(hand_id, header, domain);
        it = active_interactions_.find(hand_id);
        if (it == active_interactions_.end() || !it->second.is_active) {
            return;
        }
    }
    if (active_interaction_ids_.find(it->second.interaction_id) == active_interaction_ids_.end()) {
        return;
    }

    it->second.last_update = std::chrono::steady_clock::now();

    core::ContinuousActionUpdate update{};
    update.header = header;
    update.interaction_id = it->second.interaction_id;
    update.hand_id = hand_id;
    update.domain = it->second.domain;
    update.delta = intent.value;
    update.source_label = intent.source_label;
    update.semantic_label = intent.semantic_label;
    update.index_x = intent.index_x;
    update.index_y = intent.index_y;
    update.thumb_x = intent.thumb_x;
    update.thumb_y = intent.thumb_y;
    update_publisher_.publish(update);
}

void DecisionEngine::emit_stop_for_hand(
    const int hand_id,
    const core::EventHeader& header) {
    auto it = active_interactions_.find(hand_id);
    if (it == active_interactions_.end() || !it->second.is_active) {
        return;
    }

    core::ContinuousActionStop stop{};
    stop.header = header;
    stop.interaction_id = it->second.interaction_id;
    stop.hand_id = hand_id;
    stop.domain = it->second.domain;
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
}

bool DecisionEngine::is_continuous_adjust(const core::IntentEvent& intent) const {
    return intent.source == core::InputSource::Gesture &&
           intent.intent == core::IntentKind::Adjust;
}

}  // namespace spider::decision
