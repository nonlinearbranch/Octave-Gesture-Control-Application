#pragma once

#include <memory>
#include <utility>

#include "bus/bounded_channel.hpp"

namespace spider::bus {

template <typename T>
class EventBus final {
public:
    explicit EventBus(std::size_t capacity)
        : channel_(std::make_shared<BoundedChannel<T>>(capacity)) {}

    Publisher<T> create_publisher() const {
        return Publisher<T>(channel_);
    }

    Subscriber<T> create_subscriber() const {
        return Subscriber<T>(channel_);
    }

    void close() const {
        if (channel_) {
            channel_->close();
        }
    }

private:
    std::shared_ptr<BoundedChannel<T>> channel_;
};

}  // namespace spider::bus
