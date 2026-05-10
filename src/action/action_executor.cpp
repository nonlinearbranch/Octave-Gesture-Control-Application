#include "action/action_executor.hpp"

#include <chrono>
#include <thread>

#include "action/desktop_actions.hpp"
#include "core/logging.hpp"
#include "heuristics/HeuristicsTracker.hpp"

namespace spider::action {

ActionExecutor::ActionExecutor(
    bus::Subscriber<core::ContinuousActionStart> start_subscriber,
    bus::Subscriber<core::ContinuousActionUpdate> update_subscriber,
    bus::Subscriber<core::ContinuousActionStop> stop_subscriber)
    : start_subscriber_(std::move(start_subscriber)),
      update_subscriber_(std::move(update_subscriber)),
      stop_subscriber_(std::move(stop_subscriber)),
      heuristics_tracker_(std::make_shared<spider::heuristics::HeuristicsTracker>()) {}

void ActionExecutor::run(std::atomic<bool>& running) {
    core::ContinuousActionStart start{};
    core::ContinuousActionUpdate update{};
    core::ContinuousActionStop stop{};

    while (running.load()) {
        bool processed = false;

        if (stop_subscriber_.try_pop(stop)) {
            process_stop(stop);
            processed = true;
        }

        if (start_subscriber_.try_pop(start)) {
            process_start(start);
            processed = true;
        }

        if (update_subscriber_.try_pop(update)) {
            process_update(update);
            processed = true;
        }

        if (!processed) {
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }

    while (stop_subscriber_.try_pop(stop)) {
        process_stop(stop);
    }
    while (start_subscriber_.try_pop(start)) {
        process_start(start);
    }
    while (update_subscriber_.try_pop(update)) {
        process_update(update);
    }
}

void ActionExecutor::process_start(const core::ContinuousActionStart& start) {
    if (active_execution_.is_active) {
        return;
    }

    active_execution_.interaction_id = start.interaction_id;
    active_execution_.domain = start.domain;
    active_execution_.is_active = true;

    core::log_line(
        "[Action Start] Interaction ",
        start.interaction_id,
        " Domain ",
        core::to_string(start.domain));
}

void ActionExecutor::process_update(const core::ContinuousActionUpdate& update) {
    if (!active_execution_.is_active ||
        update.interaction_id != active_execution_.interaction_id) {
        return;
    }

    if (update.domain == core::ContinuousDomain::Cursor) {
        if (heuristics_tracker_) {
            heuristics_tracker_->process_payload(
                update.source_label,
                update.semantic_label,
                update.index_x,
                update.index_y,
                update.thumb_x,
                update.thumb_y);
        }
    } else {
        desktop_actions::apply_continuous_update(update.domain, update.delta);
    }

    core::log_line(
        "[Action Update] Interaction ",
        update.interaction_id,
        " Domain ",
        core::to_string(update.domain),
        " Delta ",
        update.delta);
}

void ActionExecutor::process_stop(const core::ContinuousActionStop& stop) {
    if (!active_execution_.is_active ||
        stop.interaction_id != active_execution_.interaction_id) {
        return;
    }

    core::log_line(
        "[Action Stop] Interaction ",
        stop.interaction_id,
        " Domain ",
        core::to_string(stop.domain));

    if (heuristics_tracker_) {
        heuristics_tracker_->enter_idle();
    }

    active_execution_ = ActiveExecution{};
}

}  // namespace spider::action
