#pragma once

#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "core/context_snapshot.hpp"

namespace spider::context {

class ContextRegistry final {
public:
    explicit ContextRegistry(std::string file_path);

    core::ContextMode classify_by_process(const std::string& process_name) const;
    core::ContextMode classify_by_domain(const std::string& domain) const;
    static core::ContextMode string_to_mode(const std::string& mode_str);

private:
    void load();
    static std::string normalize_key(std::string value);

    std::string file_path_;
    std::vector<std::pair<std::string, core::ContextMode>> process_rules_;
    std::unordered_map<std::string, core::ContextMode> domain_rules_;
};

}  // namespace spider::context
