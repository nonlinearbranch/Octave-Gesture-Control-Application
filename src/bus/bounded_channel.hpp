#pragma once

#include <condition_variable>
#include <cstddef>
#include <deque>
#include <memory>
#include <mutex>
#include <thread>
#include <utility>

namespace spider::bus {

template <typename T>
class IPublisher {
public:
    virtual ~IPublisher() = default;
    virtual bool publish(const T& value) = 0;
};

template <typename T>
class ISubscriber {
public:
    virtual ~ISubscriber() = default;
    virtual bool wait_and_pop(T& out) = 0;
    virtual bool try_pop(T& out) = 0;
};

template <typename T>
class BoundedChannel final {
public:
    explicit BoundedChannel(std::size_t capacity) : capacity_(capacity > 0 ? capacity : 1U) {}

    bool publish(const T& value) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (closed_ || queue_.size() >= capacity_) {
            return false;
        }

        queue_.push_back(value);
        cv_.notify_one();
        return true;
    }

    bool wait_and_pop(T& out) {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait(lock, [this] { return closed_ || !queue_.empty(); });

        if (queue_.empty()) {
            return false;
        }

        out = std::move(queue_.front());
        queue_.pop_front();
        return true;
    }

    bool try_pop(T& out) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (queue_.empty()) {
            return false;
        }

        out = std::move(queue_.front());
        queue_.pop_front();
        return true;
    }

    void close() {
        std::lock_guard<std::mutex> lock(mutex_);
        closed_ = true;
        cv_.notify_all();
    }

private:
    std::size_t capacity_;
    std::deque<T> queue_;
    bool closed_{false};
    std::mutex mutex_;
    std::condition_variable cv_;
};

template <typename T>
class Publisher final : public IPublisher<T> {
public:
    explicit Publisher(std::shared_ptr<BoundedChannel<T>> channel) : channel_(std::move(channel)) {}

    bool publish(const T& value) override {
        return channel_ && channel_->publish(value);
    }

private:
    std::shared_ptr<BoundedChannel<T>> channel_;
};

template <typename T>
class Subscriber final : public ISubscriber<T> {
public:
    explicit Subscriber(std::shared_ptr<BoundedChannel<T>> channel) : channel_(std::move(channel)) {}

    bool wait_and_pop(T& out) override {
        return channel_ && channel_->wait_and_pop(out);
    }

    bool try_pop(T& out) override {
        return channel_ && channel_->try_pop(out);
    }

private:
    std::shared_ptr<BoundedChannel<T>> channel_;
};

}  // namespace spider::bus
