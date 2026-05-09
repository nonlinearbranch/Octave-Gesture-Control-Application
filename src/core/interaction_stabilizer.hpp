#pragma once

#include <atomic>
#include <deque>
#include <memory>
#include <optional>
#include <string>

#include "bus/event_bus.hpp"
#include "core/gesture_event.hpp"
#include "runtime/mode_manager.hpp"

namespace spider::core {

class InteractionStabilizer final {
public:
    struct GestureWindow {
        std::deque<GestureEvent> history{};
        static constexpr std::size_t window_size = 5U;
    };

    InteractionStabilizer(
        bus::Subscriber<GestureEvent> raw_gesture_subscriber,
        bus::Publisher<GestureEvent> stable_gesture_publisher,
        std::shared_ptr<runtime::ModeManager> mode_manager);

    void run(std::atomic<bool>& running);

private:
    static bool is_continuous_label(const std::string& label);
    static float raw_delta_for_gesture(const GestureEvent& gesture);
    std::optional<GestureEvent> confirmed_gesture() const;
    float smooth_delta(float raw_delta);
    void trim_history();

    bus::Subscriber<GestureEvent> raw_gesture_subscriber_;
    bus::Publisher<GestureEvent> stable_gesture_publisher_;
    std::shared_ptr<runtime::ModeManager> mode_manager_;
    GestureWindow window_{};
    std::deque<float> delta_history_{};
    std::string last_confirmed_label_{};
    float last_published_delta_{0.0F};
    bool continuous_active_{false};
};

}  // namespace spider::core
