#pragma once

#include <string>

#include "core/continuous_action.hpp"

namespace spider::action::desktop_actions {

bool execute_discrete_action(const std::string& action_id);
void apply_continuous_update(core::ContinuousDomain domain, float delta);
const char* describe_action(const std::string& action_id);

}  // namespace spider::action::desktop_actions
