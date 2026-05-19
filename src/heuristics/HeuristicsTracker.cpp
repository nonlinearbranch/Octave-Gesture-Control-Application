#include "heuristics/HeuristicsTracker.hpp"
#include <algorithm>  // for std::min, std::max

#include <algorithm>
#include <cmath>
#include <chrono>
#ifdef _WIN32
#    include <windows.h>
#endif

namespace spider::heuristics {

namespace {

static uint64_t get_current_time_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count();
}

bool icontains(std::string_view haystack, std::string_view needle) {
    const auto lower_haystack = std::string(haystack);
    const auto lower_needle = std::string(needle);
    return std::search(
               lower_haystack.begin(),
               lower_haystack.end(),
               lower_needle.begin(),
               lower_needle.end(),
               [](unsigned char a, unsigned char b) {
                   return std::tolower(a) == std::tolower(b);
               }) != lower_haystack.end();
}

float lerp(float start, float end, float alpha) noexcept {
    return start + alpha * (end - start);
}

int normalized_to_screen(float normalized, int screen_size) noexcept {
    return static_cast<int>(std::round(normalized * static_cast<float>(screen_size - 1)));
}

}  // namespace

HeuristicsTracker::HeuristicsTracker() {
#ifdef _WIN32
    screen_width_ = GetSystemMetrics(SM_CXSCREEN);
    screen_height_ = GetSystemMetrics(SM_CYSCREEN);
#else
    screen_width_ = 1920;
    screen_height_ = 1080;
#endif
}

void HeuristicsTracker::process_payload(
    const std::string& gesture_label,
    const std::string& mode,
    float index_x,
    float index_y,
    float thumb_x,
    float thumb_y) {

    const Mode next_mode = mode_from_string(mode, gesture_label);
    set_mode(next_mode);

    if (!valid_normalized_coordinate(index_x) || !valid_normalized_coordinate(index_y)) {
        ensure_left_button_released();
        return;
    }

    switch (current_mode_) {
    case Mode::CURSOR_MODE:
        process_cursor(index_x, index_y, thumb_x, thumb_y);
        break;
    case Mode::SCROLL_MODE:
        process_scroll(index_y);
        break;
    case Mode::IDLE:
    default:
        ensure_left_button_released();
        break;
    }
}

HeuristicsTracker::Mode HeuristicsTracker::mode_from_string(
    const std::string& mode,
    const std::string& label) {
    const std::string mode_text = normalize_string(mode);
    const std::string label_text = normalize_string(label);

    if (icontains(mode_text, "cursor") || icontains(mode_text, "point") ||
        icontains(mode_text, "mouse") || icontains(mode_text, "grab and drag") ||
        icontains(mode_text, "context drag")) {
        return Mode::CURSOR_MODE;
    }
    if (icontains(mode_text, "scroll") || icontains(mode_text, "magnitude")) {
        return Mode::SCROLL_MODE;
    }

    if (icontains(label_text, "cursor") || icontains(label_text, "point") ||
        icontains(label_text, "pinch") || icontains(label_text, "index")) {
        return Mode::CURSOR_MODE;
    }
    if (icontains(label_text, "scroll") || icontains(label_text, "wheel")) {
        return Mode::SCROLL_MODE;
    }

    return Mode::IDLE;
}

std::string HeuristicsTracker::normalize_string(std::string_view value) {
    std::string normalized(value);
    std::transform(
        normalized.begin(),
        normalized.end(),
        normalized.begin(),
        [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
    return normalized;
}

void HeuristicsTracker::set_mode(Mode next_mode) {
    if (next_mode == current_mode_) {
        return;
    }

    if (left_pressed_) {
        emit_mouse_up();
    }

    current_mode_ = next_mode;
    first_cursor_frame_ = true;
    has_last_scroll_ = false;
}

void HeuristicsTracker::enter_idle() {
    set_mode(Mode::IDLE);
}

void HeuristicsTracker::process_cursor(
    float index_x,
    float index_y,
    float thumb_x,
    float thumb_y) {
    update_pinch_state(index_x, index_y, thumb_x, thumb_y);
    update_cursor_position(index_x, index_y);
}

void HeuristicsTracker::process_scroll(float index_y) {
    if (!valid_normalized_coordinate(index_y)) {
        return;
    }

    if (!has_last_scroll_) {
        last_scroll_y_ = index_y;
        has_last_scroll_ = true;
        return;
    }

    const float delta_y = last_scroll_y_ - index_y;
    last_scroll_y_ = index_y;

    const float threshold = 0.012F;
    if (std::fabs(delta_y) < threshold) {
        return;
    }

    const int wheel_delta = static_cast<int>(std::round(delta_y * 120.0F * 4.0F));
    emit_mouse_wheel(clamp_x(wheel_delta, -480, 480));
}

void HeuristicsTracker::update_cursor_position(float index_x, float index_y) {
    uint64_t now = get_current_time_ms();
    if (now < freeze_cursor_until_ms_) {
        last_raw_index_x_ = index_x;
        last_raw_index_y_ = index_y;
        return;
    }

    if (first_cursor_frame_) {
        last_raw_index_x_ = index_x;
        last_raw_index_y_ = index_y;
#ifdef _WIN32
        POINT p;
        if (GetCursorPos(&p)) {
            last_cursor_x_ = static_cast<float>(p.x);
            last_cursor_y_ = static_cast<float>(p.y);
        } else {
            last_cursor_x_ = static_cast<float>(screen_width_ / 2);
            last_cursor_y_ = static_cast<float>(screen_height_ / 2);
        }
#else
        last_cursor_x_ = static_cast<float>(screen_width_ / 2);
        last_cursor_y_ = static_cast<float>(screen_height_ / 2);
#endif
        first_cursor_frame_ = false;
        return;
    }

    const float delta_x = index_x - last_raw_index_x_;
    const float delta_y = index_y - last_raw_index_y_;
    last_raw_index_x_ = index_x;
    last_raw_index_y_ = index_y;

    const float raw_movement = std::sqrt(delta_x * delta_x + delta_y * delta_y);

    if (raw_movement < 0.0005F) {
        return;
    }

    float acceleration = 1.0F + (raw_movement * 40.0F);
    
    float target_x_delta = delta_x * static_cast<float>(screen_width_) * 1.5F * acceleration;
    float target_y_delta = delta_y * static_cast<float>(screen_height_) * 1.5F * acceleration;

    float target_x = last_cursor_x_ + target_x_delta;
    float target_y = last_cursor_y_ + target_y_delta;
    
    target_x = std::max(0.0F, std::min(static_cast<float>(screen_width_ - 1), target_x));
    target_y = std::max(0.0F, std::min(static_cast<float>(screen_height_ - 1), target_y));

    float dynamic_alpha = std::max(0.15F, std::min(1.0F, raw_movement * 15.0F));

    float next_x = lerp(last_cursor_x_, target_x, dynamic_alpha);
    float next_y = lerp(last_cursor_y_, target_y, dynamic_alpha);

    last_cursor_x_ = next_x;
    last_cursor_y_ = next_y;

    SetCursorPos(static_cast<int>(std::round(next_x)), static_cast<int>(std::round(next_y)));
}

void HeuristicsTracker::update_pinch_state(
    float index_x,
    float index_y,
    float thumb_x,
    float thumb_y) {
    if (!valid_normalized_coordinate(thumb_x) || !valid_normalized_coordinate(thumb_y)) {
        return;
    }

    const float dx = thumb_x - index_x;
    const float dy = thumb_y - index_y;
    const float distance = std::sqrt(dx * dx + dy * dy);

    if (distance < click_enter_threshold_ && !left_pressed_) {
        emit_mouse_down();
        freeze_cursor_until_ms_ = get_current_time_ms() + 200;
    } else if (distance > click_exit_threshold_ && left_pressed_) {
        emit_mouse_up();
        freeze_cursor_until_ms_ = get_current_time_ms() + 100;
    }
}

void HeuristicsTracker::ensure_left_button_released() {
    if (left_pressed_) {
        emit_mouse_up();
    }
}

bool HeuristicsTracker::valid_normalized_coordinate(float value) noexcept {
    return !std::isnan(value) && value >= 0.0F && value <= 1.0F;
}

int HeuristicsTracker::clamp_x(int value, int min_value, int max_value) noexcept {
    return std::max(min_value, std::min(max_value, value));
}

int HeuristicsTracker::clamp_y(int value, int min_value, int max_value) noexcept {
    return std::max(min_value, std::min(max_value, value));
}

void HeuristicsTracker::emit_mouse_down() {
#ifdef _WIN32
    INPUT input{};
    input.type = INPUT_MOUSE;
    input.mi.dwFlags = MOUSEEVENTF_LEFTDOWN;
    SendInput(1, &input, sizeof(input));
#endif
    left_pressed_ = true;
}

void HeuristicsTracker::emit_mouse_up() {
#ifdef _WIN32
    INPUT input{};
    input.type = INPUT_MOUSE;
    input.mi.dwFlags = MOUSEEVENTF_LEFTUP;
    SendInput(1, &input, sizeof(input));
#endif
    left_pressed_ = false;
}

void HeuristicsTracker::emit_mouse_wheel(int delta) {
#ifdef _WIN32
    INPUT input{};
    input.type = INPUT_MOUSE;
    input.mi.dwFlags = MOUSEEVENTF_WHEEL;
    input.mi.mouseData = static_cast<DWORD>(delta);
    SendInput(1, &input, sizeof(input));
#endif
}

}  // namespace spider::heuristics
