from intent_engine.context_engine.contextual_intent_engine import infer_intent

override_member = None
override_timer = 0
OVERRIDE_DURATION = 5.0

import time


def set_override(member):
    global override_member, override_timer
    override_member = member
    override_timer = time.time()


def get_active_intent(gesture_family, semantic_features):
    global override_member, override_timer

    if override_member:
        if time.time() - override_timer < OVERRIDE_DURATION:
            return override_member, 1.0
        else:
            override_member = None

    return infer_intent(gesture_family, semantic_features)
