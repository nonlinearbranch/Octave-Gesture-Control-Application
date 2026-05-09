#pragma once

#include <atomic>
#include <cstdint>

#include "bus/event_bus.hpp"
#include "core/continuous_action.hpp"

namespace spider::action {

class ActionExecutor final {
public:
    struct ActiveExecution {
        std::uint64_t interaction_id{0};
        core::ContinuousDomain domain{core::ContinuousDomain::Adjust};
        bool is_active{false};
    };

    ActionExecutor(
        bus::Subscriber<core::ContinuousActionStart> start_subscriber,
        bus::Subscriber<core::ContinuousActionUpdate> update_subscriber,
        bus::Subscriber<core::ContinuousActionStop> stop_subscriber);

    void run(std::atomic<bool>& running);

private:
    void process_start(const core::ContinuousActionStart& start);
    void process_update(const core::ContinuousActionUpdate& update);
    void process_stop(const core::ContinuousActionStop& stop);

    bus::Subscriber<core::ContinuousActionStart> start_subscriber_;
    bus::Subscriber<core::ContinuousActionUpdate> update_subscriber_;
    bus::Subscriber<core::ContinuousActionStop> stop_subscriber_;
    ActiveExecution active_execution_{};
};

}  // namespace spider::action
