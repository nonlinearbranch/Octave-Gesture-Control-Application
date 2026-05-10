#include "intent/gesture_mapping_registry.hpp"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <sstream>

namespace spider::intent {

namespace {

const char* to_storage_value(const core::IntentKind intent) {
    switch (intent) {
    case core::IntentKind::Scroll:
        return "Scroll";
    case core::IntentKind::Adjust:
        return "Adjust";
    case core::IntentKind::Select:
    default:
        return "Select";
    }
}

core::IntentKind from_storage_value(const std::string& value) {
    if (value == "Scroll") {
        return core::IntentKind::Scroll;
    }
    if (value == "Adjust") {
        return core::IntentKind::Adjust;
    }
    return core::IntentKind::Select;
}

core::IntentKind intent_for_action(const std::string& action) {
    if (action.find("Mode:") == 0 || action == "Adjust") {
        return core::IntentKind::Adjust;
    }
    if (action.find("Scroll") != std::string::npos) {
        return core::IntentKind::Scroll;
    }
    return core::IntentKind::Select;
}

std::size_t find_matching_pair(const std::string& text, std::size_t start, char open_char, char close_char) {
    if (start >= text.size() || text[start] != open_char) {
        return std::string::npos;
    }
    int depth = 0;
    for (std::size_t pos = start; pos < text.size(); ++pos) {
        if (text[pos] == open_char) {
            ++depth;
        } else if (text[pos] == close_char) {
            --depth;
            if (depth == 0) {
                return pos;
            }
        }
    }
    return std::string::npos;
}

std::string trim(const std::string& text) {
    std::size_t begin = 0;
    while (begin < text.size() && std::isspace(static_cast<unsigned char>(text[begin]))) {
        ++begin;
    }
    std::size_t end = text.size();
    while (end > begin && std::isspace(static_cast<unsigned char>(text[end - 1]))) {
        --end;
    }
    return text.substr(begin, end - begin);
}

std::string extract_json_section(const std::string& text, const std::string& key) {
    const std::string token = '"' + key + '"';
    const auto pos = text.find(token);
    if (pos == std::string::npos) {
        return {};
    }
    auto colon = text.find(':', pos + token.size());
    if (colon == std::string::npos) {
        return {};
    }
    auto value_start = colon + 1;
    while (value_start < text.size() && std::isspace(static_cast<unsigned char>(text[value_start]))) {
        ++value_start;
    }
    if (value_start >= text.size()) {
        return {};
    }
    const char open_char = text[value_start];
    const char close_char = open_char == '{' ? '}' : (open_char == '[' ? ']' : '\0');
    if (close_char == '\0') {
        return {};
    }
    const auto end_pos = find_matching_pair(text, value_start, open_char, close_char);
    if (end_pos == std::string::npos) {
        return {};
    }
    return text.substr(value_start, end_pos - value_start + 1);
}

std::string extract_json_string_value(const std::string& text, const std::string& key) {
    const std::string search = '"' + key + '"';
    auto pos = text.find(search);
    if (pos == std::string::npos) {
        return {};
    }
    pos = text.find(':', pos + search.size());
    if (pos == std::string::npos) {
        return {};
    }
    ++pos;
    while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos]))) {
        ++pos;
    }
    if (pos >= text.size() || text[pos] != '"') {
        return {};
    }
    const auto end_quote = text.find('"', pos + 1);
    if (end_quote == std::string::npos) {
        return {};
    }
    return text.substr(pos + 1, end_quote - pos - 1);
}

std::unordered_map<std::string, GestureBinding> parse_gesture_map(const std::string& section) {
    std::unordered_map<std::string, GestureBinding> result;
    auto pos = std::size_t{0};
    while (pos < section.size()) {
        const auto key_start = section.find('"', pos);
        if (key_start == std::string::npos) {
            break;
        }
        const auto key_end = section.find('"', key_start + 1);
        if (key_end == std::string::npos) {
            break;
        }
        const auto label = section.substr(key_start + 1, key_end - key_start - 1);
        const auto object_start = section.find('{', key_end + 1);
        if (object_start == std::string::npos) {
            break;
        }
        const auto object_end = find_matching_pair(section, object_start, '{', '}');
        if (object_end == std::string::npos) {
            break;
        }
        const auto object_text = section.substr(object_start, object_end - object_start + 1);
        const auto intent = extract_json_string_value(object_text, "intent");
        const auto action = extract_json_string_value(object_text, "action");
        GestureBinding binding{
            intent.empty() ? intent_for_action(action) : from_storage_value(intent),
            action.empty() ? "Click" : action};
        result.emplace(label, std::move(binding));
        pos = object_end + 1;
    }
    return result;
}

std::unordered_map<std::string, GestureBinding> parse_model_mapping_section(const std::string& section) {
    std::unordered_map<std::string, GestureBinding> result;
    auto pos = std::size_t{0};
    while (pos < section.size()) {
        const auto key_start = section.find('"', pos);
        if (key_start == std::string::npos) {
            break;
        }
        const auto key_end = section.find('"', key_start + 1);
        if (key_end == std::string::npos) {
            break;
        }
        const auto object_start = section.find('{', key_end + 1);
        if (object_start == std::string::npos) {
            break;
        }
        const auto object_end = find_matching_pair(section, object_start, '{', '}');
        if (object_end == std::string::npos) {
            break;
        }
        const auto object_text = section.substr(object_start, object_end - object_start + 1);
        const auto name = extract_json_string_value(object_text, "name");
        const auto action = extract_json_string_value(object_text, "action");
        if (!name.empty() && action != "None") {
            const std::string resolved_action = action.empty() ? "Click" : action;
            result[name] = GestureBinding{intent_for_action(resolved_action), resolved_action};
        }
        pos = object_end + 1;
    }
    return result;
}

std::unordered_map<std::string, int> parse_model_mapping_indices(const std::string& section) {
    std::unordered_map<std::string, int> result;
    auto pos = std::size_t{0};
    while (pos < section.size()) {
        const auto key_start = section.find('"', pos);
        if (key_start == std::string::npos) {
            break;
        }
        const auto key_end = section.find('"', key_start + 1);
        if (key_end == std::string::npos) {
            break;
        }
        int index = 0;
        try {
            index = std::stoi(section.substr(key_start + 1, key_end - key_start - 1));
        } catch (...) {
            pos = key_end + 1;
            continue;
        }
        const auto object_start = section.find('{', key_end + 1);
        if (object_start == std::string::npos) {
            break;
        }
        const auto object_end = find_matching_pair(section, object_start, '{', '}');
        if (object_end == std::string::npos) {
            break;
        }
        const auto object_text = section.substr(object_start, object_end - object_start + 1);
        const auto name = extract_json_string_value(object_text, "name");
        if (!name.empty()) {
            result[name] = index;
        }
        pos = object_end + 1;
    }
    return result;
}

std::unordered_map<std::string, std::string> parse_string_map(const std::string& section) {
    std::unordered_map<std::string, std::string> result;
    auto pos = std::size_t{0};
    while (pos < section.size()) {
        const auto key_start = section.find('"', pos);
        if (key_start == std::string::npos) {
            break;
        }
        const auto key_end = section.find('"', key_start + 1);
        if (key_end == std::string::npos) {
            break;
        }
        const auto key = section.substr(key_start + 1, key_end - key_start - 1);
        auto value_start = section.find('"', key_end + 1);
        if (value_start == std::string::npos) {
            break;
        }
        const auto value_end = section.find('"', value_start + 1);
        if (value_end == std::string::npos) {
            break;
        }
        const auto value = section.substr(value_start + 1, value_end - value_start - 1);
        result.emplace(key, value);
        pos = value_end + 1;
    }
    return result;
}

std::unordered_set<std::string> parse_string_array(const std::string& section) {
    std::unordered_set<std::string> result;
    auto pos = std::size_t{0};
    while (pos < section.size()) {
        const auto value_start = section.find('"', pos);
        if (value_start == std::string::npos) {
            break;
        }
        const auto value_end = section.find('"', value_start + 1);
        if (value_end == std::string::npos) {
            break;
        }
        result.emplace(section.substr(value_start + 1, value_end - value_start - 1));
        pos = value_end + 1;
    }
    return result;
}

std::string escape_json_string(const std::string& value) {
    std::string output;
    output.reserve(value.size());
    for (const char ch : value) {
        switch (ch) {
        case '\\': output += "\\\\"; break;
        case '"': output += "\\\""; break;
        case '\n': output += "\\n"; break;
        case '\r': output += "\\r"; break;
        case '\t': output += "\\t"; break;
        default: output += ch; break;
        }
    }
    return output;
}

bool load_file_text(const std::filesystem::path& path, std::string& contents) {
    std::ifstream input(path);
    if (!input.is_open()) {
        return false;
    }
    std::ostringstream buffer;
    buffer << input.rdbuf();
    contents = buffer.str();
    return true;
}

void merge_maps(std::unordered_map<std::string, GestureBinding>& target,
                const std::unordered_map<std::string, GestureBinding>& source) {
    for (const auto& pair : source) {
        target[pair.first] = pair.second;
    }
}

void merge_maps(std::unordered_map<std::string, std::string>& target,
                const std::unordered_map<std::string, std::string>& source) {
    for (const auto& pair : source) {
        target[pair.first] = pair.second;
    }
}

void merge_sets(std::unordered_set<std::string>& target,
                const std::unordered_set<std::string>& source) {
    target.insert(source.begin(), source.end());
}

}  // namespace

GestureMappingRegistry::GestureMappingRegistry(std::string config_dir)
    : config_dir_(std::move(config_dir)) {
    load();
}

std::optional<core::IntentKind> GestureMappingRegistry::resolve(const std::string& label) const {
    const auto binding = resolve_gesture(label);
    if (!binding.has_value()) {
        return std::nullopt;
    }
    return binding->intent;
}

std::optional<GestureBinding> GestureMappingRegistry::resolve_gesture(const std::string& label) const {
    std::lock_guard<std::mutex> lock(mutex_);
    if (disabled_static_.find(label) != disabled_static_.end()) {
        return std::nullopt;
    }
    const auto it = gesture_mappings_.find(label);
    if (it == gesture_mappings_.end()) {
        return std::nullopt;
    }
    if (it->second.action == "None") {
        return std::nullopt;
    }
    return it->second;
}

std::optional<std::string> GestureMappingRegistry::resolve_voice_action(const std::string& phrase) const {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto it = voice_actions_.find(phrase);
    if (it == voice_actions_.end()) {
        return std::nullopt;
    }
    return it->second;
}

void GestureMappingRegistry::register_label(
    const std::string& label,
    const core::IntentKind intent,
    const std::string& action) {
    std::unique_lock<std::mutex> lock(mutex_);
    gesture_mappings_[label] = GestureBinding{intent, action.empty() ? "Click" : action};
    user_labels_.insert(label);
    save();
}

bool GestureMappingRegistry::update_gesture(
    const std::string& old_label,
    const std::string& new_label,
    const std::string& action) {
    std::unique_lock<std::mutex> lock(mutex_);
    const auto source = !old_label.empty() ? old_label : new_label;
    auto it = gesture_mappings_.find(source);
    GestureBinding binding{};
    if (it != gesture_mappings_.end()) {
        binding = it->second;
        if (old_label != new_label && !old_label.empty()) {
            gesture_mappings_.erase(it);
        }
    } else {
        const std::string effective_action = action.empty() ? "Click" : action;
        const core::IntentKind intent =
            effective_action == "Adjust" ? core::IntentKind::Adjust :
            (effective_action == "ScrollUp" || effective_action == "ScrollDown")
                ? core::IntentKind::Scroll
                : core::IntentKind::Select;
        binding = GestureBinding{intent, effective_action};
    }

    if (!action.empty()) {
        binding.action = action;
        if (action == "Adjust") {
            binding.intent = core::IntentKind::Adjust;
        } else if (action == "ScrollUp" || action == "ScrollDown") {
            binding.intent = core::IntentKind::Scroll;
        } else {
            binding.intent = core::IntentKind::Select;
        }
    }

    gesture_mappings_[new_label] = binding;
    user_labels_.erase(old_label);
    user_labels_.insert(new_label);
    save();
    return true;
}

void GestureMappingRegistry::upsert_voice_action(const std::string& phrase, const std::string& action) {
    std::unique_lock<std::mutex> lock(mutex_);
    voice_actions_[phrase] = action.empty() ? "Click" : action;
    save();
}

void GestureMappingRegistry::delete_label(const std::string& label) {
    std::unique_lock<std::mutex> lock(mutex_);
    if (user_labels_.find(label) != user_labels_.end()) {
        gesture_mappings_.erase(label);
        user_labels_.erase(label);
    }
    save();
}

void GestureMappingRegistry::delete_voice_action(const std::string& phrase) {
    std::unique_lock<std::mutex> lock(mutex_);
    voice_actions_.erase(phrase);
    save();
}

std::vector<std::string> GestureMappingRegistry::list_labels() const {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<std::string> labels;
    labels.reserve(gesture_mappings_.size());
    for (const auto& entry : gesture_mappings_) {
        labels.push_back(entry.first);
    }
    return labels;
}

std::unordered_map<std::string, std::string> GestureMappingRegistry::list_static_actions() const {
    std::lock_guard<std::mutex> lock(mutex_);
    std::unordered_map<std::string, std::string> actions;
    for (const auto& entry : gesture_mappings_) {
        actions.emplace(entry.first, entry.second.action);
    }
    return actions;
}

std::unordered_map<std::string, std::string> GestureMappingRegistry::list_voice_actions() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return voice_actions_;
}

std::vector<std::string> GestureMappingRegistry::list_disabled_static() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return std::vector<std::string>(disabled_static_.begin(), disabled_static_.end());
}

void GestureMappingRegistry::set_disabled_static(const std::vector<std::string>& disabled) {
    std::unique_lock<std::mutex> lock(mutex_);
    disabled_static_.clear();
    disabled_static_.insert(disabled.begin(), disabled.end());
    save();
}

void GestureMappingRegistry::load() {
    std::unordered_map<std::string, GestureBinding> loaded_gestures;
    std::unordered_map<std::string, std::string> loaded_voice_actions;
    std::unordered_set<std::string> loaded_disabled;
    std::unordered_set<std::string> loaded_user_labels;

    std::filesystem::path config_dir(config_dir_);
    const std::filesystem::path default_path = config_dir / "default_mapping.json";
    const std::filesystem::path user_path = config_dir / "user_mapping.json";
    std::string contents;

    if (load_file_text(default_path, contents)) {
        merge_maps(loaded_gestures, parse_model_mapping_section(extract_json_section(contents, "static")));
        merge_maps(loaded_gestures, parse_model_mapping_section(extract_json_section(contents, "dynamic")));
        merge_maps(loaded_gestures, parse_gesture_map(extract_json_section(contents, "gestures")));
        merge_maps(loaded_voice_actions, parse_string_map(extract_json_section(contents, "voice_actions")));
        merge_sets(loaded_disabled, parse_string_array(extract_json_section(contents, "disabled_static")));
    }

    if (load_file_text(user_path, contents)) {
        const auto user_static = parse_model_mapping_section(extract_json_section(contents, "static"));
        const auto user_dynamic = parse_model_mapping_section(extract_json_section(contents, "dynamic"));
        for (const auto& entry : user_static) {
            loaded_user_labels.insert(entry.first);
        }
        for (const auto& entry : user_dynamic) {
            loaded_user_labels.insert(entry.first);
        }
        merge_maps(loaded_gestures, user_static);
        merge_maps(loaded_gestures, user_dynamic);
        merge_maps(loaded_voice_actions, parse_string_map(extract_json_section(contents, "voice_actions")));
        merge_sets(loaded_disabled, parse_string_array(extract_json_section(contents, "disabled_static")));
    }

    {
        std::unique_lock<std::mutex> lock(mutex_);
        gesture_mappings_ = std::move(loaded_gestures);
        voice_actions_ = std::move(loaded_voice_actions);
        disabled_static_ = std::move(loaded_disabled);
        user_labels_ = std::move(loaded_user_labels);
    }

    save();
}

void GestureMappingRegistry::save() const {
    const auto gesture_copy = gesture_mappings_;
    const auto voice_copy = voice_actions_;
    const auto disabled_copy = disabled_static_;
    const auto user_label_copy = user_labels_;

    std::filesystem::path config_dir(config_dir_);
    std::filesystem::create_directories(config_dir);
    const std::filesystem::path output_path = config_dir / "user_mapping.json";
    std::unordered_map<std::string, int> existing_indices;
    std::unordered_map<std::string, int> existing_dynamic_indices;
    std::unordered_map<std::string, std::string> existing_dynamic_actions;
    std::string existing_contents;
    if (load_file_text(output_path, existing_contents)) {
        existing_indices = parse_model_mapping_indices(extract_json_section(existing_contents, "static"));
        existing_dynamic_indices = parse_model_mapping_indices(extract_json_section(existing_contents, "dynamic"));
        const auto dynamic_section = extract_json_section(existing_contents, "dynamic");
        const auto parsed_dynamic = parse_model_mapping_section(dynamic_section);
        for (const auto& entry : parsed_dynamic) {
            existing_dynamic_actions[entry.first] = entry.second.action;
        }
    }
    int next_index = 0;
    int next_dynamic_index = 0;
    for (const auto& entry : existing_indices) {
        next_index = std::max(next_index, entry.second + 1);
    }
    for (const auto& entry : existing_dynamic_indices) {
        next_dynamic_index = std::max(next_dynamic_index, entry.second + 1);
    }

    std::ofstream output(output_path, std::ios::trunc);
    if (!output.is_open()) {
        return;
    }

    output << "{\n";
    output << "  \"static\": {\n";
    bool first_gesture = true;
    for (const auto& entry : gesture_copy) {
        if (user_label_copy.find(entry.first) == user_label_copy.end()) {
            continue;
        }
        int label_index = next_index++;
        const auto existing = existing_indices.find(entry.first);
        if (existing != existing_indices.end()) {
            label_index = existing->second;
        }
        if (!first_gesture) {
            output << ",\n";
        }
        first_gesture = false;
        output << "    \"" << label_index << "\": {\n";
        output << "      \"name\": \"" << escape_json_string(entry.first) << "\"";
        output << ",\n      \"action\": \"" << escape_json_string(entry.second.action) << "\"\n";
        output << "    }";
    }
    output << "\n  },\n";

    output << "  \"dynamic\": {\n";
    bool first_dynamic = true;
    for (const auto& entry : existing_dynamic_actions) {
        int label_index = next_dynamic_index++;
        const auto existing = existing_dynamic_indices.find(entry.first);
        if (existing != existing_dynamic_indices.end()) {
            label_index = existing->second;
        }
        if (!first_dynamic) {
            output << ",\n";
        }
        first_dynamic = false;
        output << "    \"" << label_index << "\": {\n";
        output << "      \"name\": \"" << escape_json_string(entry.first) << "\"";
        output << ",\n      \"action\": \"" << escape_json_string(entry.second) << "\"\n";
        output << "    }";
    }
    output << "\n  },\n";

    output << "  \"voice_actions\": {\n";
    bool first_voice = true;
    for (const auto& entry : voice_copy) {
        if (!first_voice) {
            output << ",\n";
        }
        first_voice = false;
        output << "    \"" << escape_json_string(entry.first) << "\": \"" << escape_json_string(entry.second) << "\"";
    }
    output << "\n  },\n";

    output << "  \"disabled_static\": [\n";
    bool first_disabled = true;
    for (const auto& entry : disabled_copy) {
        if (!first_disabled) {
            output << ",\n";
        }
        first_disabled = false;
        output << "    \"" << escape_json_string(entry) << "\"";
    }
    output << "\n  ]\n";
    output << "}\n";
}

}  // namespace spider::intent
