#include "runtime/mode_manager.hpp"

#include <mutex>

namespace spider::runtime {

InteractionMode ModeManager::getMode() {
    std::lock_guard<std::mutex> lock(mode_mutex_);
    return current_mode_;
}

bool ModeManager::setMode(const InteractionMode mode) {
    std::lock_guard<std::mutex> lock(mode_mutex_);
    if (current_mode_ == mode) {
        return false;
    }

    current_mode_ = mode;
    return true;
}

const char* to_string(const InteractionMode mode) {
    switch (mode) {
    case InteractionMode::HAND:
        return "HAND";
    case InteractionMode::VOICE:
        return "VOICE";
    default:
        return "UNKNOWN";
    }
}

}  // namespace spider::runtime
