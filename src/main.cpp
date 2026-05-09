#include <chrono>
#include <iostream>
#include <thread>

#include "runtime/pipeline_demo.hpp"

int main() {
    spider::runtime::PipelineDemo demo;
    demo.start();

    std::cout << "SPIDER engine running.\n";
    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}
