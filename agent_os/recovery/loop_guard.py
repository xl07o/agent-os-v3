"""
loop_guard.py - حماية الحلقات اللانهائية (Infinite Loop Protection) — §35
=========================================================================
الاستقلالية لا تعني الدوران للأبد. يكشف: تكرار نفس الفعل، تكرار نفس الخطأ،
عدم التقدم، التذبذب (A→B→A→B)، والاهتزاز — ثم يوصي بتغيير الاستراتيجية.
"""

import os
import sys

def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C


class LoopGuard:
    """يراقب سلسلة أفعال/نتائج ويكتشف الأنماط العقيمة."""

    def __init__(self, repeat_limit=3, window=8):
        self.actions = []       # (action, outcome)
        self.repeat_limit = repeat_limit
        self.window = window

    def record(self, action, outcome="", progressed=False):
        self.actions.append({"action": str(action), "outcome": str(outcome),
                             "progressed": bool(progressed)})
        self.actions = self.actions[-self.window * 2:]

    def _same_action_repeated(self):
        """نفس الفعل تكرر repeat_limit مرة متتالية."""
        if len(self.actions) < self.repeat_limit:
            return False
        recent = [a["action"] for a in self.actions[-self.repeat_limit:]]
        return len(set(recent)) == 1

    def _same_error_repeated(self):
        recent = [a["outcome"] for a in self.actions[-self.repeat_limit:]
                  if a["outcome"]]
        return len(recent) >= self.repeat_limit and len(set(recent)) == 1

    def _no_progress(self):
        """لا تقدّم خلال النافذة رغم أفعال متعددة."""
        window = self.actions[-self.window:]
        return len(window) >= self.window and not any(a["progressed"] for a in window)

    def _oscillation(self):
        """تذبذب A→B→A→B (فعلان يتبادلان بلا تقدم)."""
        window = [a["action"] for a in self.actions[-4:]]
        if len(window) < 4:
            return False
        return window[0] == window[2] and window[1] == window[3] and window[0] != window[1]

    def check(self):
        """يعيد حكماً: هل ندور بلا فائدة؟ وما التوصية؟"""
        problems = []
        if self._same_action_repeated():
            problems.append("تكرار نفس الفعل")
        if self._same_error_repeated():
            problems.append("تكرار نفس الخطأ")
        if self._no_progress():
            problems.append("لا تقدّم")
        if self._oscillation():
            problems.append("تذبذب")

        stuck = bool(problems)
        return {
            "stuck": stuck,
            "problems": problems,
            "recommendation": "غيّر الاستراتيجية أو صعّد للإنسان" if stuck else "استمر",
            "actions_seen": len(self.actions),
        }

    def reset(self):
        self.actions = []


if __name__ == "__main__":
    g = LoopGuard()
    for _ in range(4):
        g.record("retry_fetch", outcome="timeout", progressed=False)
    print(g.check())
    g.reset()
    for a in ["A", "B", "A", "B"]:
        g.record(a, progressed=False)
    print(g.check())
