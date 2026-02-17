from collections import deque
from dynamic_engine.motion_utils import distance


class DynamicFamilyDetector:
    def __init__(self):
        self.prev_index = None
        self.prev_angle = None
        self.history = deque(maxlen=6)

    def _extended(self, hand, tip, pip):
        return hand.landmark[tip].y < hand.landmark[pip].y

    def _finger_state(self, hand):
        thumb = hand.landmark[4].x > hand.landmark[3].x
        index = self._extended(hand, 8, 6)
        middle = self._extended(hand, 12, 10)
        ring = self._extended(hand, 16, 14)
        pinky = self._extended(hand, 20, 18)
        return {
            "thumb": thumb,
            "index": index,
            "middle": middle,
            "ring": ring,
            "pinky": pinky
        }

    def _classify_once(self, hand):
        fs = self._finger_state(hand)
        count = sum(1 for v in fs.values() if v)

        pinch_d = distance(hand.landmark[4], hand.landmark[8])
        if pinch_d < 0.035:
            return "GRAB"

        if fs["index"] and fs["middle"] and not fs["ring"] and not fs["pinky"]:
            return "SCROLL"

        if count >= 4:
            return "MAGNITUDE"

        index_tip = hand.landmark[8]
        idx = (index_tip.x, index_tip.y)

        wrist = hand.landmark[0]
        index_mcp = hand.landmark[5]
        angle = index_mcp.x - wrist.x

        family = None

        if fs["index"] and not fs["middle"] and not fs["ring"] and not fs["pinky"]:
            if self.prev_index is not None:
                dx = idx[0] - self.prev_index[0]
                dy = idx[1] - self.prev_index[1]
                if abs(dx) > 0.03 and abs(dx) > abs(dy) * 1.4:
                    family = "NAVIGATION"
                else:
                    family = "CURSOR"
            else:
                family = "CURSOR"

        if family is None and count >= 2:
            if self.prev_angle is not None:
                da = abs(angle - self.prev_angle)
                if da > 0.02:
                    family = "ROTATION"

        self.prev_index = idx
        self.prev_angle = angle

        return family

    def detect(self, hand):
        fam = self._classify_once(hand)
        if fam is None:
            return None
        self.history.append(fam)
        if len(self.history) < self.history.maxlen:
            return fam
        counts = {}
        for x in self.history:
            counts[x] = counts.get(x, 0) + 1
        best = max(counts, key=counts.get)
        return best
