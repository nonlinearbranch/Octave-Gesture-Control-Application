cmake_minimum_required(VERSION 3.16)

project(SpiderSlice1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(spider_slice1
    src/main.cpp
    src/runtime/pipeline_demo.cpp
    src/intent/intent_normalizer.cpp
    src/intent/gesture_mapping_registry.cpp
    src/decision/decision_engine.cpp
    src/action/action_executor.cpp
    src/action/desktop_actions.cpp
    src/context/context_provider.cpp
    src/voice/voice_intent_mapper.cpp
    src/runtime/mode_manager.cpp
    src/ipc/python_ml_service_client.cpp
    src/ipc/engine_command_server.cpp
    src/ipc/python_service_process.cpp
    src/heuristics/HeuristicsTracker.cpp
)

target_include_directories(spider_slice1 PRIVATE src)
target_link_libraries(spider_slice1 PRIVATE ws2_32 user32 shell32 dxva2)
