#include "context/context_registry.hpp"

#include <algorithm>
#include <cctype>
#include <utility>
#include <fstream>

#include "core/logging.hpp"

#ifdef _WIN32
#include <nlohmann/json.hpp>
#endif

namespace spider::context {

ContextRegistry::ContextRegistry(std::string file_path)
    : file_path_(std::move(file_path)) {
    load();
}

core::ContextMode ContextRegistry::classify_by_process(const std::string& process_name) const {
    const std::string normalized = normalize_key(process_name);
    for (const auto& [key, mode] : process_rules_) {
        if (normalized.find(key) != std::string::npos) {
            return mode;
        }
    }
    return core::ContextMode::Desktop;
}

core::ContextMode ContextRegistry::classify_by_domain(const std::string& domain) const {
    const std::string normalized = normalize_key(domain);
    const auto it = domain_rules_.find(normalized);
    if (it == domain_rules_.end()) {
        return core::ContextMode::Unknown;
    }
    return it->second;
}

core::ContextMode ContextRegistry::string_to_mode(const std::string& mode_str) {
    const std::string normalized = normalize_key(mode_str);
    if (normalized == "browser") {
        return core::ContextMode::Browser;
    }
    if (normalized == "media") {
        return core::ContextMode::Media;
    }
    if (normalized == "editor") {
        return core::ContextMode::Editor;
    }
    if (normalized == "design") {
        return core::ContextMode::Design;
    }
    if (normalized == "presentation") {
        return core::ContextMode::Presentation;
    }
    if (normalized == "conferencing") {
        return core::ContextMode::Conferencing;
    }
    if (normalized == "gaming") {
        return core::ContextMode::Gaming;
    }
    if (normalized == "desktop") {
        return core::ContextMode::Desktop;
    }
    return core::ContextMode::Unknown;
}

void ContextRegistry::load() {
#ifdef _WIN32
    process_rules_.clear();
    domain_rules_.clear();

    std::ifstream input(file_path_);
    if (!input.is_open()) {
        core::log_line("[ContextRegistry] Failed to open ", file_path_);
        return;
    }

    nlohmann::json parsed;
    try {
        input >> parsed;
    } catch (const std::exception& exc) {
        core::log_line("[ContextRegistry] Failed to parse ", file_path_, " error=", exc.what());
        return;
    }

    const auto processes = parsed.contains("processes") ? parsed["processes"] : nlohmann::json::object();
    if (processes.is_object()) {
        for (auto it = processes.begin(); it != processes.end(); ++it) {
            if (!it.value().is_string()) {
                continue;
            }
            process_rules_.emplace_back(
                normalize_key(it.key()),
                string_to_mode(it.value().get<std::string>()));
        }
    }

    std::sort(
        process_rules_.begin(),
        process_rules_.end(),
        [](const auto& left, const auto& right) {
            if (left.first.size() != right.first.size()) {
                return left.first.size() > right.first.size();
            }
            return left.first < right.first;
        });

    const auto domains = parsed.contains("domains") ? parsed["domains"] : nlohmann::json::object();
    if (domains.is_object()) {
        for (auto it = domains.begin(); it != domains.end(); ++it) {
            if (!it.value().is_string()) {
                continue;
            }
            domain_rules_[normalize_key(it.key())] = string_to_mode(it.value().get<std::string>());
        }
    }

    core::log_line(
        "[ContextRegistry] Loaded processes=",
        process_rules_.size(),
        " domains=",
        domain_rules_.size(),
        " from ",
        file_path_);
#else
    process_rules_.clear();
    domain_rules_.clear();
#endif
}

std::string ContextRegistry::normalize_key(std::string value) {
    std::transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
    return value;
}

}  // namespace spider::context
