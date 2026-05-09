#pragma once

#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <unordered_set>
#include <unordered_map>
#include <vector>

#include "core/intent_event.hpp"

namespace spider::intent {

struct GestureBinding {
    core::IntentKind intent{core::IntentKind::Select};
    std::string action{"Click"};
};

class GestureMappingRegistry final {
public:
    explicit GestureMappingRegistry(std::string config_dir);

    std::optional<core::IntentKind> resolve(const std::string& label) const;
    std::optional<GestureBinding> resolve_gesture(const std::string& label) const;
    std::optional<std::string> resolve_voice_action(const std::string& phrase) const;
    void register_label(
        const std::string& label,
        core::IntentKind intent = core::IntentKind::Select,
        const std::string& action = "Click");
    bool update_gesture(const std::string& old_label, const std::string& new_label, const std::string& action);
    void upsert_voice_action(const std::string& phrase, const std::string& action);
    void delete_label(const std::string& label);
    void delete_voice_action(const std::string& phrase);
    std::vector<std::string> list_labels() const;
    std::unordered_map<std::string, std::string> list_static_actions() const;
    std::unordered_map<std::string, std::string> list_voice_actions() const;
    std::vector<std::string> list_disabled_static() const;
    void set_disabled_static(const std::vector<std::string>& disabled);

private:
    void load();
    void save() const;

    std::string config_dir_;
    mutable std::mutex mutex_;
    std::unordered_map<std::string, GestureBinding> gesture_mappings_;
    std::unordered_map<std::string, std::string> voice_actions_;
    std::unordered_set<std::string> disabled_static_;
    std::unordered_set<std::string> user_labels_;
};

}  // namespace spider::intent
