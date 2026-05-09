#include "ipc/python_service_process.hpp"

#include <filesystem>
#include <string>
#include <cstring>
#include <cctype>

#include "core/logging.hpp"

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#endif

namespace spider::ipc {

#ifdef _WIN32
namespace {

bool equals_ignore_case(const std::string& lhs, const std::string& rhs) {
    if (lhs.size() != rhs.size()) {
        return false;
    }
    for (std::size_t index = 0; index < lhs.size(); ++index) {
        if (std::tolower(static_cast<unsigned char>(lhs[index])) !=
            std::tolower(static_cast<unsigned char>(rhs[index]))) {
            return false;
        }
    }
    return true;
}

std::filesystem::path find_project_root_from(const std::filesystem::path& start) {
    auto candidate = start;
    while (!candidate.empty()) {
        if (std::filesystem::exists(candidate / "CMakeLists.txt") &&
            std::filesystem::exists(candidate / "src")) {
            return candidate;
        }
        const auto parent = candidate.parent_path();
        if (parent == candidate) {
            break;
        }
        candidate = parent;
    }
    return start;
}

std::string build_environment_block(
    const std::filesystem::path& interpreter_path,
    const std::filesystem::path& vosk_model) {
    const LPCH raw_environment = GetEnvironmentStringsA();
    if (raw_environment == nullptr) {
        return {};
    }

    std::string environment_block;
    std::string inherited_path;
    for (LPCCH current = raw_environment; *current != '\0'; current += std::strlen(current) + 1) {
        std::string entry(current, std::strlen(current));
        const auto separator = entry.find('=');
        if (separator == std::string::npos) {
            continue;
        }
        const std::string name = entry.substr(0, separator);
        const std::string value = entry.substr(separator + 1);

        if (equals_ignore_case(name, "PATH")) {
            if (inherited_path.empty()) {
                inherited_path = value;
            }
            continue;
        }
        if (equals_ignore_case(name, "PYTHONHOME") || equals_ignore_case(name, "PYTHONPATH")) {
            continue;
        }

        environment_block.append(entry);
        environment_block.push_back('\0');
    }

    FreeEnvironmentStringsA(raw_environment);

    std::string normalized_path = interpreter_path.parent_path().string();
    if (!inherited_path.empty()) {
        normalized_path.append(";");
        normalized_path.append(inherited_path);
    }
    environment_block.append("PATH=");
    environment_block.append(normalized_path);
    environment_block.push_back('\0');

    if (std::filesystem::exists(vosk_model)) {
        environment_block.append("SPIDER_VOSK_MODEL_DIR=");
        environment_block.append(vosk_model.string());
        environment_block.push_back('\0');
    }

    environment_block.append("PYTHONNOUSERSITE=1");
    environment_block.push_back('\0');

    environment_block.push_back('\0');
    return environment_block;
}

}  // namespace
#endif

PythonServiceProcess::PythonServiceProcess() = default;

PythonServiceProcess::~PythonServiceProcess() {
    stop();
}

std::filesystem::path PythonServiceProcess::resolve_project_root() {
    char module_path[MAX_PATH]{};
    const DWORD length = GetModuleFileNameA(nullptr, module_path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        return find_project_root_from(std::filesystem::current_path());
    }

    return find_project_root_from(std::filesystem::path(module_path).parent_path());
}

std::string PythonServiceProcess::resolve_python_executable() {
    const auto root = resolve_project_root();
    const auto venv_python = root / ".venv" / "Scripts" / "python.exe";
    if (std::filesystem::exists(venv_python)) {
        return venv_python.string();
    }
    const auto venv_pythonw = root / ".venv" / "Scripts" / "pythonw.exe";
    if (std::filesystem::exists(venv_pythonw)) {
        return venv_pythonw.string();
    }

    const auto py310 =
        std::filesystem::path("C:\\Users\\HP\\AppData\\Local\\Programs\\Python\\Python310\\python.exe");
    if (std::filesystem::exists(py310)) {
        return py310.string();
    }

    return "python";
}

bool PythonServiceProcess::start(const std::string& working_directory, const std::string& script_path) {
#ifndef _WIN32
    return false;
#else
    if (running_) {
        return true;
    }

    STARTUPINFOA startup_info{};
    startup_info.cb = sizeof(startup_info);
    ZeroMemory(&process_info_, sizeof(process_info_));

    const auto root = resolve_project_root();
    const auto venv_python = root / ".venv" / "Scripts" / "python.exe";
    const auto venv_pythonw = root / ".venv" / "Scripts" / "pythonw.exe";
    const auto py310 =
        std::filesystem::path("C:\\Users\\HP\\AppData\\Local\\Programs\\Python\\Python310\\python.exe");
    const std::string fallback_python = "python";
    const std::string interpreters[] = {
        venv_python.string(),
        venv_pythonw.string(),
        py310.string(),
        fallback_python,
    };

    const auto vosk_model =
        root / "vosk-model-small-en-us-0.15" / "vosk-model-small-en-us-0.15";
    const auto service_working_directory =
        (root / working_directory).lexically_normal().string();
    const auto service_script =
        (root / working_directory / script_path).lexically_normal().string();

    for (const auto& interpreter : interpreters) {
        if (interpreter.empty()) {
            continue;
        }
        const std::string environment_block =
            build_environment_block(std::filesystem::path(interpreter), vosk_model);
        ZeroMemory(&process_info_, sizeof(process_info_));
        std::string command = "\"" + interpreter + "\" \"" + service_script + "\"";
        if (CreateProcessA(
                interpreter.c_str(),
                command.data(),
                nullptr,
                nullptr,
                FALSE,
                CREATE_NO_WINDOW,
                environment_block.empty() ? nullptr : const_cast<char*>(environment_block.data()),
                service_working_directory.c_str(),
                &startup_info,
                &process_info_)) {
            const DWORD wait_result = WaitForSingleObject(process_info_.hProcess, 750);
            if (wait_result == WAIT_TIMEOUT) {
                core::log_line("[IPC] Python service started with ", interpreter);
                running_ = true;
                return true;
            }

            DWORD exit_code = 0;
            GetExitCodeProcess(process_info_.hProcess, &exit_code);
            core::log_line(
                "[IPC] Python service exited immediately for ",
                interpreter,
                " exit=",
                exit_code);
            CloseHandle(process_info_.hThread);
            CloseHandle(process_info_.hProcess);
            ZeroMemory(&process_info_, sizeof(process_info_));
            continue;
        }
        core::log_line("[IPC] Python service launch failed for ", interpreter, " error=", GetLastError());
    }
    return false;
#endif
}

void PythonServiceProcess::stop() {
#ifdef _WIN32
    if (!running_) {
        return;
    }

    // Wait for graceful exit (SHUTDOWN was sent via TCP by PipelineDemo::stop)
    const DWORD wait_result = WaitForSingleObject(process_info_.hProcess, 2000);
    if (wait_result != WAIT_OBJECT_0) {
        // Graceful shutdown timed out — force kill as fallback
        core::log_line("[IPC] Python service did not exit gracefully, force-killing");
        TerminateProcess(process_info_.hProcess, 0);
        WaitForSingleObject(process_info_.hProcess, 1000);
    }

    CloseHandle(process_info_.hThread);
    CloseHandle(process_info_.hProcess);
    ZeroMemory(&process_info_, sizeof(process_info_));
    running_ = false;
#endif
}

}  // namespace spider::ipc
