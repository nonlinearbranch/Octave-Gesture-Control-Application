#pragma once

#include <filesystem>
#include <string>

#ifdef _WIN32
#include <windows.h>
#endif

namespace spider::ipc {

class PythonServiceProcess final {
public:
    PythonServiceProcess();
    ~PythonServiceProcess();

    bool start(const std::string& working_directory, const std::string& script_path);
    void stop();

private:
#ifdef _WIN32
    static std::string resolve_python_executable();
    static std::filesystem::path resolve_project_root();
    PROCESS_INFORMATION process_info_{};
    bool running_{false};
#endif
};

}  // namespace spider::ipc
