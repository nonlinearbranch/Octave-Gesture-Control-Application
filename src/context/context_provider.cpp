#include "context/context_provider.hpp"

#include <cctype>
#include <chrono>
#include <string>
#include <thread>

#include "core/logging.hpp"

#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#endif

namespace spider::context {

#ifdef _WIN32
namespace {

std::string get_foreground_process_name() {
    const HWND foreground = GetForegroundWindow();
    if (foreground == nullptr) {
        return {};
    }

    DWORD process_id = 0;
    GetWindowThreadProcessId(foreground, &process_id);
    if (process_id == 0) {
        return {};
    }

    const HANDLE process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, process_id);
    if (process == nullptr) {
        return {};
    }

    char path[MAX_PATH]{};
    DWORD path_size = MAX_PATH;
    std::string name;
    if (QueryFullProcessImageNameA(process, 0, path, &path_size)) {
        name = path;
        const auto slash = name.find_last_of("\\/");
        if (slash != std::string::npos) {
            name = name.substr(slash + 1);
        }
        for (auto& ch : name) {
            ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
        }
    }

    CloseHandle(process);
    return name;
}

std::string get_foreground_window_title() {
    const HWND foreground = GetForegroundWindow();
    if (foreground == nullptr) {
        return {};
    }

    char title[256]{};
    GetWindowTextA(foreground, title, sizeof(title));
    return title;
}

core::ContextMode classify_process(const std::string& process_name) {
    if (process_name.find("powerpnt") != std::string::npos ||
        process_name.find("keynote") != std::string::npos ||
        process_name.find("impress") != std::string::npos) {
        return core::ContextMode::Presentation;
    }

    if (process_name.find("zoom") != std::string::npos ||
        process_name.find("teams") != std::string::npos ||
        process_name.find("webex") != std::string::npos ||
        process_name.find("slack") != std::string::npos ||
        process_name.find("discord") != std::string::npos) {
        return core::ContextMode::Conferencing;
    }

    if (process_name.find("photoshop") != std::string::npos ||
        process_name.find("illustrator") != std::string::npos ||
        process_name.find("figma") != std::string::npos ||
        process_name.find("blender") != std::string::npos ||
        process_name.find("sketch") != std::string::npos) {
        return core::ContextMode::Design;
    }

    if (process_name.find("steam") != std::string::npos ||
        process_name.find("epicgameslauncher") != std::string::npos ||
        process_name.find("riotclient") != std::string::npos ||
        process_name.find("valorant") != std::string::npos ||
        process_name.find("cs2") != std::string::npos ||
        process_name.find("dota") != std::string::npos) {
        return core::ContextMode::Gaming;
    }

    if (process_name.find("chrome") != std::string::npos ||
        process_name.find("firefox") != std::string::npos ||
        process_name.find("msedge") != std::string::npos ||
        process_name.find("opera") != std::string::npos ||
        process_name.find("brave") != std::string::npos ||
        process_name.find("electron") != std::string::npos ||
        process_name.find("spider-ui") != std::string::npos ||
        process_name.find("node") != std::string::npos) {
        return core::ContextMode::Browser;
    }

    if (process_name.find("vlc") != std::string::npos ||
        process_name.find("spotify") != std::string::npos ||
        process_name.find("wmplayer") != std::string::npos ||
        process_name.find("groove") != std::string::npos ||
        process_name.find("itunes") != std::string::npos ||
        process_name.find("mpv") != std::string::npos) {
        return core::ContextMode::Media;
    }

    if (process_name.find("code") != std::string::npos ||
        process_name.find("devenv") != std::string::npos ||
        process_name.find("notepad") != std::string::npos ||
        process_name.find("sublime") != std::string::npos ||
        process_name.find("idea") != std::string::npos ||
        process_name.find("clion") != std::string::npos) {
        return core::ContextMode::Editor;
    }

    return core::ContextMode::Desktop;
}

}  // namespace
#endif

ContextProvider::ContextProvider(bus::Publisher<core::ContextSnapshot> publisher)
    : publisher_(std::move(publisher)) {}

void ContextProvider::run(std::atomic<bool>& running) {
    std::uint64_t sequence_number = 1U;
    core::ContextMode previous_mode = core::ContextMode::Unknown;

    while (running.load()) {
#ifdef _WIN32
        const std::string process_name = get_foreground_process_name();
        const std::string window_title = get_foreground_window_title();
        const core::ContextMode mode = process_name.empty()
            ? core::ContextMode::Desktop
            : classify_process(process_name);
#else
        const std::string process_name = "unknown";
        const std::string window_title = "Unknown";
        const core::ContextMode mode = core::ContextMode::Desktop;
#endif

        if (mode != previous_mode) {
            core::ContextSnapshot snapshot{};
            snapshot.header.sequence_number = sequence_number++;
            snapshot.header.timestamp = std::chrono::steady_clock::now();
            snapshot.app_id = process_name;
            snapshot.window_title = window_title;
            snapshot.context_mode = mode;

            if (publisher_.publish(snapshot)) {
                core::log_line("[Context] ", core::to_string(mode), " (", process_name, ")");
            }

            previous_mode = mode;
        }

        for (int step = 0; step < 5 && running.load(); ++step) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
}

}  // namespace spider::context
