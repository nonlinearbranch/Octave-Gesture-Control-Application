#pragma once

#include <string>

namespace spider::heuristics {

class HeuristicsTracker final {
public:
    HeuristicsTracker();
    void enter_idle();
    void process_payload(
        const std::string& gesture_label,
        const std::string& mode,
        float index_x,
        float index_y,
        float thumb_x,
        float thumb_y);

private:
    enum class Mode {
        IDLE,
        CURSOR_MODE,
        SCROLL_MODE,
    };

    static Mode mode_from_string(const std::string& mode, const std::string& label);
    static std::string normalize_string(std::string_view value);

    void set_mode(Mode next_mode);
    
    void process_cursor(float index_x, float index_y, float thumb_x, float thumb_y);
    void process_scroll(float index_y);
    void update_cursor_position(float index_x, float index_y);
    void update_pinch_state(float index_x, float index_y, float thumb_x, float thumb_y);
    void ensure_left_button_released();
    static bool valid_normalized_coordinate(float value) noexcept;
    static int clamp_x(int value, int min_value, int max_value) noexcept;
    static int clamp_y(int value, int min_value, int max_value) noexcept;

    void emit_mouse_down();
    void emit_mouse_up();
    void emit_mouse_wheel(int delta);

    Mode current_mode_{Mode::IDLE};
    bool left_pressed_{false};
    int screen_width_{0};
    int screen_height_{0};
    float last_cursor_x_{0.0F};
    float last_cursor_y_{0.0F};
    float last_scroll_y_{0.0F};
    bool has_last_scroll_{false};
    bool first_cursor_frame_{true};
    float last_raw_index_x_{0.0F};
    float last_raw_index_y_{0.0F};
    uint64_t freeze_cursor_until_ms_{0};
    float smoothing_alpha_{0.60F};
    float click_enter_threshold_{0.05F};
    float click_exit_threshold_{0.08F};
};

}  // namespace spider::heuristics
