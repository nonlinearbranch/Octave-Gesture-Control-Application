from intent_engine.context_engine.contextual_intent_engine import infer_intent, FAMILY_MEMBERS
from utils.helpers import get_setting

override_member = None
override_timer = 0

import time


def set_override(member):
    global override_member, override_timer
    override_member = member
    override_timer = time.time()


def get_active_intent(gesture_family, semantic_features):
    global override_member, override_timer
    override_duration = float(get_setting("override_duration_sec", 5.0))

    if override_member:
        if time.time() - override_timer < override_duration:
            return override_member, 1.0
        else:
            override_member = None

    return infer_intent(gesture_family, semantic_features)


def cycle_override(gesture_family, current_member=None):
    members = FAMILY_MEMBERS.get(gesture_family) or []
    if not members:
        return None
    if current_member in members:
        i = members.index(current_member)
        member = members[(i + 1) % len(members)]
    else:
        member = members[0]
    set_override(member)
    return member
