#pragma once

#include <iostream>
#include <mutex>
#include <utility>

namespace spider::core {

inline std::mutex g_log_mutex;

template <typename... Args>
void log_line(Args&&... args) {
    std::lock_guard<std::mutex> lock(g_log_mutex);
    (std::cout << ... << std::forward<Args>(args)) << std::endl;
}

}  // namespace spider::core
