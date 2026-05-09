#include "runtime/pipeline_demo.hpp"

#include <chrono>
#include <filesystem>
#include <thread>

#include "core/logging.hpp"

#ifdef _WIN32
#include <windows.h>
#endif

namespace spider::runtime {

namespace {

std::filesystem::path resolve_project_root() {
#ifdef _WIN32
    char module_path[MAX_PATH]{};
    const DWORD length = GetModuleFileNameA(nullptr, module_path, MAX_PATH);
    if (length > 0 && length < MAX_PATH) {
        auto candidate = std::filesystem::path(module_path).parent_path();
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
    }
#endif
    return std::filesystem::current_path();
}

}  // namespace

PipelineDemo::PipelineDemo()
    : project_root_(resolve_project_root()),
      gesture_bus_(16U),
      voice_bus_(16U),
      intent_bus_(16U),
      context_bus_(16U),
      continuous_start_bus_(16U),
      continuous_update_bus_(16U),
      continuous_stop_bus_(16U),
      mode_manager_(std::make_shared<ModeManager>()),
      mapping_registry_(std::make_shared<intent::GestureMappingRegistry>(
          (project_root_ / "ml" / "config").string())),
      heuristics_tracker_(std::make_shared<spider::heuristics::HeuristicsTracker>()),
      ml_service_client_(std::make_shared<ipc::PythonMlServiceClient>(
          gesture_bus_.create_publisher(),
          voice_bus_.create_publisher(),
          heuristics_tracker_,
          "127.0.0.1",
          50555,
          mapping_registry_)),
      command_server_(ml_service_client_, mapping_registry_, mode_manager_,
          voice_bus_.create_publisher()),
      intent_normalizer_(
          gesture_bus_.create_subscriber(),
          voice_bus_.create_subscriber(),
          intent_bus_.create_publisher(),
          mode_manager_,
          mapping_registry_,
          ml_service_client_),
      context_provider_(context_bus_.create_publisher()),
      decision_engine_(
          intent_bus_.create_subscriber(),
          context_bus_.create_subscriber(),
          continuous_start_bus_.create_publisher(),
          continuous_update_bus_.create_publisher(),
          continuous_stop_bus_.create_publisher(),
          mode_manager_),
      action_executor_(
          continuous_start_bus_.create_subscriber(),
          continuous_update_bus_.create_subscriber(),
          continuous_stop_bus_.create_subscriber()) {}

PipelineDemo::~PipelineDemo() {
    stop();
}

void PipelineDemo::start() {
    bool expected = false;
    if (!running_.compare_exchange_strong(expected, true)) {
        return;
    }

    std::filesystem::current_path(project_root_);
    core::log_line("[Mode] ", to_string(mode_manager_->getMode()));
    python_service_process_.start("ml", "service.py");
    std::this_thread::sleep_for(std::chrono::milliseconds(750));

    ml_service_thread_ =
        std::thread([this] { ml_service_client_->run(running_); });
    command_server_thread_ =
        std::thread([this] { command_server_.run(running_); });
    intent_thread_ =
        std::thread([this] { intent_normalizer_.run(running_); });
    context_thread_ =
        std::thread([this] { context_provider_.run(running_); });
    decision_thread_ =
        std::thread([this] { decision_engine_.run(running_); });
    action_thread_ =
        std::thread([this] { action_executor_.run(running_); });
}

void PipelineDemo::stop() {
    bool expected = true;
    if (!running_.compare_exchange_strong(expected, false)) {
        return;
    }

    gesture_bus_.close();
    voice_bus_.close();
    intent_bus_.close();
    context_bus_.close();
    continuous_start_bus_.close();
    continuous_update_bus_.close();
    continuous_stop_bus_.close();
    ml_service_client_->send_shutdown();
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    ml_service_client_->disconnect();

    if (ml_service_thread_.joinable()) {
        ml_service_thread_.join();
    }
    if (command_server_thread_.joinable()) {
        command_server_thread_.join();
    }
    if (intent_thread_.joinable()) {
        intent_thread_.join();
    }
    if (context_thread_.joinable()) {
        context_thread_.join();
    }
    if (decision_thread_.joinable()) {
        decision_thread_.join();
    }
    if (action_thread_.joinable()) {
        action_thread_.join();
    }

    python_service_process_.stop();
}

}  // namespace spider::runtime
