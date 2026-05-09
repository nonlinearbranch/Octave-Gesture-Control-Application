#pragma once

#include <atomic>

#include "bus/event_bus.hpp"
#include "core/context_snapshot.hpp"

namespace spider::context {

class ContextProvider final {
public:
    explicit ContextProvider(bus::Publisher<core::ContextSnapshot> publisher);

    void run(std::atomic<bool>& running);

private:
    bus::Publisher<core::ContextSnapshot> publisher_;
};

}  // namespace spider::context
