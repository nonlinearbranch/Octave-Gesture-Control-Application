#pragma once

#include <atomic>
#include <cstdint>
#include <memory>
#include <string>

#include "bus/event_bus.hpp"
#include "core/voice_event.hpp"
#include "intent/gesture_mapping_registry.hpp"
#include "ipc/python_ml_service_client.hpp"
#include "runtime/mode_manager.hpp"

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#endif

namespace spider::ipc {

class EngineCommandServer final {
public:
    EngineCommandServer(
        std::shared_ptr<PythonMlServiceClient> ml_client,
        std::shared_ptr<intent::GestureMappingRegistry> mapping_registry,
        std::shared_ptr<runtime::ModeManager> mode_manager,
        bus::Publisher<core::VoiceEvent> voice_publisher,
        std::uint16_t port = 50556);

    void run(std::atomic<bool>& running);

private:
    std::string handle_command(const std::string& line);
    static std::string extract_string(const std::string& json, const std::string& key);
    static double extract_number(const std::string& json, const std::string& key, double fallback);
    static std::string escape_json(const std::string& value);

    std::shared_ptr<PythonMlServiceClient> ml_client_;
    std::shared_ptr<intent::GestureMappingRegistry> mapping_registry_;
    std::shared_ptr<runtime::ModeManager> mode_manager_;
    bus::Publisher<core::VoiceEvent> voice_publisher_;
    std::uint16_t port_;
    std::uint64_t voice_sequence_{1};
};

}  // namespace spider::ipc
