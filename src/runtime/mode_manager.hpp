#pragma once

#include <mutex>

namespace spider::runtime {

enum class InteractionMode {
    HAND,
    VOICE
};

class ModeManager final {
public:
    InteractionMode getMode();
    bool setMode(InteractionMode mode);

private:
    InteractionMode current_mode_{InteractionMode::HAND};
    std::mutex mode_mutex_;
};

const char* to_string(InteractionMode mode);

}  // namespace spider::runtime
