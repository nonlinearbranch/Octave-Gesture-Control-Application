#include "core/interaction_stabilizer.hpp"

#include <array>
#include <chrono>
#include <cmath>
#include <thread>

#include "core/logging.hpp"

namespace spider::core {

namespace {

constexpr int kConfirmationThreshold = 3;
constexpr std::size_t kDeltaWindowSize = 3U;
constexpr float kDeltaThreshold = 0.02F;

}  // namespace

InteractionStabilizer::InteractionStabilizer(
    bus::Subscriber<GestureEvent> raw_gesture_subscriber,
    bus::Publisher<GestureEvent> stable_gesture_publisher,
    std::shared_ptr<runtime::ModeManager> mode_manager)
    : raw_gesture_subscriber_(std::move(raw_gesture_subscriber)),
      stable_gesture_publisher_(std::move(stable_gesture_publisher)),
      mode_manager_(std::move(mode_manager)) {}

void InteractionStabilizer::run(std::atomic<bool>& running) {
    GestureEvent gesture{};

    while (running.load()) {
        if (!raw_gesture_subscriber_.wait_and_pop(gesture)) {
            break;
        }

        if (mode_manager_ &&
            mode_manager_->getMode() != runtime::InteractionMode::HAND) {
            window_.history.clear();
            delta_history_.clear();
            last_confirmed_label_.clear();
            continuous_active_ = false;
            last_published_delta_ = 0.0F;
            continue;
        }

        window_.history.push_back(gesture);
        trim_history();

        const auto maybe_confirmed = confirmed_gesture();
        if (!maybe_confirmed.has_value()) {
            continue;
        }

        GestureEvent stable = *maybe_confirmed;
        const bool label_changed = stable.label != last_confirmed_label_;
        const bool is_continuous = is_continuous_label(stable.label);

        if (label_changed) {
            core::log_line("[Stabilizer] Gesture Confirmed ", stable.label);
            if (is_continuous && !continuous_active_) {
                core::log_line("[Stabilizer] Start Confirmed");
            }
            if (!is_continuous && continuous_active_) {
                core::log_line("[Stabilizer] Stop Confirmed");
            }
        }

        if (!is_continuous) {
            delta_history_.clear();
            last_published_delta_ = 0.0F;

            if (label_changed && stable_gesture_publisher_.publish(stable)) {
                last_confirmed_label_ = stable.label;
                continuous_active_ = false;
            }
            continue;
        }

        const float smoothed = smooth_delta(raw_delta_for_gesture(stable));
        if (!label_changed &&
            std::fabs(smoothed - last_published_delta_) <= kDeltaThreshold) {
            continue;
        }

        stable.confidence = 0.75F + smoothed;

        if (stable_gesture_publisher_.publish(stable)) {
            core::log_line("[Stabilizer] Smoothed Delta: ", smoothed);
            last_confirmed_label_ = stable.label;
            last_published_delta_ = smoothed;
            continuous_active_ = true;
        }
    }
}

bool InteractionStabilizer::is_continuous_label(const std::string& label) {
    return label == "MOVE_HAND" || label == "PINCH";
}

float InteractionStabilizer::raw_delta_for_gesture(const GestureEvent& gesture) {
    return gesture.confidence - 0.75F;
}

std::optional<GestureEvent> InteractionStabilizer::confirmed_gesture() const {
    if (window_.history.size() < kConfirmationThreshold) {
        return std::nullopt;
    }

    std::array<std::pair<std::string, int>, 5> counts{};
    std::size_t used = 0U;

    for (const auto& gesture : window_.history) {
        bool found = false;
        for (std::size_t i = 0; i < used; ++i) {
            if (counts[i].first == gesture.label) {
                ++counts[i].second;
                found = true;
                break;
            }
        }
        if (!found && used < counts.size()) {
            counts[used] = {gesture.label, 1};
            ++used;
        }
    }

    std::string best_label{};
    int best_count = 0;
    for (std::size_t i = 0; i < used; ++i) {
        if (counts[i].second > best_count) {
            best_label = counts[i].first;
            best_count = counts[i].second;
        }
    }

    if (best_count < kConfirmationThreshold) {
        return std::nullopt;
    }

    for (auto it = window_.history.rbegin(); it != window_.history.rend(); ++it) {
        if (it->label == best_label) {
            return *it;
        }
    }

    return std::nullopt;
}

float InteractionStabilizer::smooth_delta(const float raw_delta) {
    delta_history_.push_back(raw_delta);
    while (delta_history_.size() > kDeltaWindowSize) {
        delta_history_.pop_front();
    }

    float sum = 0.0F;
    for (const float value : delta_history_) {
        sum += value;
    }

    return delta_history_.empty() ? 0.0F : (sum / static_cast<float>(delta_history_.size()));
}

void InteractionStabilizer::trim_history() {
    while (window_.history.size() > GestureWindow::window_size) {
        window_.history.pop_front();
    }
}

}  // namespace spider::core
