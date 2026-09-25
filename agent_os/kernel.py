"""
kernel.py - نواة التشغيل المستمر AgentOS (v3.0)
=================================================
يجمع الأنظمة الاثني عشر في حلقة حياة واحدة:

    تقرير مالي -> طلبات معلقة -> ضمان أهداف -> تنفيذ أهم مهمة -> تحسين ذات كل 5 دورات

قواعد:
  - لا يصنع قراراً مفتوحاً أبداً: إن لم تكن هناك مهمة جاهزة، يتوقف بصمت (لا يحترق مالاً).
  - النفقة المدفوعة محكومة بالميزانية اليومية (can_spend) — المجاني لا يُحتسب.
  - كل دورة قابلة للتوقف الآمن بين أي خطوة (لوحات لحظية، لا حلقات عنيدة).
"""

import os
import sys
import time
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C
# وحدات الدفعة 3: مشرف، حافلة أحداث، مولّد مهام — تُستدعى داخل الحلقة
from agent_os import event_bus, mission_generator, supervisor

CYCLE_FILE = os.path.join(C.AGENT_OS_DIR, "kernel_cycles.json")
HEARTBEAT_FILE = os.path.join(C.AGENT_OS_DIR, "heartbeat.json")
SELF_IMPROVE_EVERY = 5  # كل هذا العدد من الدورات نتحسن ذاتياً


class AgentOS:
    """جسد الوكيل: واجهة واحدة على كل الأنظمة، مع حلقة تشغيل مستمرة."""

    def __init__(self, use_brain=False):
        self.use_brain = use_brain
        self._lazy = {}

    # ===== وصلات متكاسلة (تُستحضر عند الحاجة فقط) =====
    def _get(self, name):
        if name not in self._lazy:
            mod = __import__(f"agent_os.{name}", fromlist=[name])
            self._lazy[name] = mod
        return self._lazy[name]

    @property
    def finance(self):
        return self._get("finance_intel")

    @property
    def approvals(self):
        return self._get("approval_center")

    @property
    def goals(self):
        return self._get("goal_manager")

    @property
    def benchmark(self):
        return self._get("benchmark")

    @property
    def self_improve(self):
        return self._get("self_improve_engine")

    @property
    def nucleus(self):
        return self._get("agent_os")

    @property
    def world(self):
        return self._get("world_model")

    @property
    def tools(self):
        return self._get("tool_registry")

    @property
    def golden(self):
        return self._get("golden_loop")

    def run_goal(self, goal_text):
        """تشغيل هدف واحد عبر الحلقة الذهبية (المواصفة §5) مستخدماً النواة كمنفّذ.

        يوحّد المسار: understand→plan→execute→verify→measure→learn.
        النواة (agent_os.run_task) تبقى الأداة المنفّذة — فلا يتغيّر الأمان،
        لكن التحقق بالأدلة يُضاف فوقها فلا يُعلَن نجاح بلا دليل (§106).
        """
        golden = self.golden

        def _executor(step):
            detail = step.get("detail") or step.get("action", "")
            res = self.nucleus.run_task(detail, use_brain=self.use_brain)
            status = res.get("result", {}).get("status", "")
            # حالات النواة الحقيقية: verified/revised = نُفّذ، needs_human = تصعيد
            ran = status in ("verified", "revised", "done", "approved")
            out = res.get("result", {}).get("output", res.get("result", {}).get("grade", ""))
            step_result = {"ran": ran, "output": f"[{status}] {str(out)[:300]}"}
            expected = res.get("result", {}).get("expected")
            if expected:
                step_result["expected"] = expected
            return step_result

        rec = golden.run(goal_text, _executor)
        if rec.get("outcome") == "failure":
            self._heal_register(goal_text, rec)
        return rec

    def _heal_register(self, goal_text, rec):
        """كل فشل صريح = درس دائم للعقل الجديد:
        يُسجَّل في failures.jsonl ويُنشر حدث self_improve_needed الذي
        تغذّي منه دورة التحسين الذاتي (self_improve_engine) تعديلاتٍ
        في فرع معزول وتختبرها قبل أي دمج على الملف الحي."""
        try:
            from agent_os import _common as C, event_bus
            import json as _json
            path = os.path.join(C.AGENT_OS_DIR, "failures.jsonl")
            entry = {
                "ts": C.now_iso(),
                "goal": goal_text[:200],
                "outcome": rec.get("outcome"),
                "intent": (rec.get("phases") or {}).get("understand", {}).get("intent"),
                "measure": rec.get("phases", {}).get("measure", {}),
                "next": rec.get("next"),
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
            try:
                event_bus.publish("self_improve_needed", {
                    "goal": goal_text[:120], "ts": entry["ts"],
                    "outcome": rec.get("outcome"), "source": "golden_loop",
                })
            except Exception:
                pass
            C.log(f"🧠 فشل مسجّل للتحسين الذاتي: {goal_text[:40]}")
        except Exception as e:
            try:
                C.log(f"⚠️ تسجيل الفشل نفسه انهار: {e}")
            except Exception:
                pass

    # ===== خطة اليوم =====

    def ensure_goals(self, max_auto=2):
        """ضمان وجود أهداف جارية: من عقل استراتيجي أو أضعف مناطق القياس.
        عند الخمول (لا أهداف نشطة) يولّد أهداف تعلم من أضعف المجالات،
        وإن حتى القياس فارغ يولّد هدفاً استكشافياً — يمنع حلقة فارغة (عيب 10/22)."""
        new_ids = []
        if not self.goals.get_active_goals():
            if not self.goals.list_goals():
                src = None
                try:
                    from agent_os import strategic_mind
                    src = strategic_mind.suggest_goals() or None
                except Exception:
                    src = None
                if not src:
                    w = self.benchmark.weakest_areas(2)
                    src = [(f"رفع كفاءة {d}", f"أضعف منطقة في القياس: {d}") for d in w] or [
                        ("توثيق نظام التشغيل", "دليل استخدام واضح لكل نظام")]
                for title, objective in src[:max_auto]:
                    g = self.goals.add_goal(title, objective, priority="medium", auto=True,
                                            category="auto")
                    try:
                        self.goals.breakdown(g["id"])
                    except Exception:
                        pass
                    new_ids.append(g["id"])
                return new_ids
            # لا أهداف نشطة رغم وجود أرشيف — نولّد من أضعف المجالات بدل الخمول
            weak = []
            try:
                weak = self.benchmark.weakest_categories(3)
            except Exception:
                weak = []
            if weak:
                for cat in weak:
                    name = cat.get("name") if isinstance(cat, dict) else str(cat)
                    score = cat.get("score", 0) if isinstance(cat, dict) else 0
                    g = self.goals.add_goal(f"تحسين مهارة: {name}",
                                            f"الدرجة الحالية: {score}/100 — المطلوب: رفعها فوق {score + 15}",
                                            priority=2, auto=True, category="auto")
                    try:
                        self.goals.breakdown(g["id"])
                    except Exception:
                        pass
                    new_ids.append(g["id"])
            else:
                # حتى القياس فارغ — هدف استكشافي ثابت
                g = self.goals.add_goal("استكشاف مصادر تعلم جديدة",
                                        "ابحث عن APIs مجانية، repos مفيدة، مهارات ناقصة",
                                        priority=3, auto=True, category="auto")
                try:
                    self.goals.breakdown(g["id"])
                except Exception:
                    pass
                new_ids.append(g["id"])
        return new_ids

    # ===== الحلقة =====

    def _heartbeat(self):
        """نبض الدورة لمراقب خارجي (watchdog) — timestamp في heartbeat.json."""
        try:
            C.atomic_write(HEARTBEAT_FILE, {"ts": time.time(), "at": C.now_iso(),
                                            "pid": os.getpid()})
        except Exception:
            pass

    def run_nightly(self, minutes=55.0, allow_self_improve=True):
        """الوضع الليلي (مقترح كلاودي #8): تشغيل مستمر خلال ساعات الليل مع تحسين ذاتي
        وخط إنتاج ليلٍ. تعود بملخص شامل."""
        issues = self._health_check()
        if issues:
            return {"mode": "nightly", "skipped": "health_failed", "issues": issues}
        run = self.run_until(minutes, max_steps=6, allow_self_improve=allow_self_improve)
        product = {}
        try:
            from agent_os import product_factory
            product = product_factory.nightly_pipeline()
        except Exception as e:
            product = {"error": str(e)[:120]}
        intel = {}
        try:
            from agent_os import opportunity_brain, revenue_engine
            intel = {"opportunities": [o["name"] for o in opportunity_brain.scan().get("opportunities", [])],
                     "revenue": revenue_engine.report()}
        except Exception as e:
            intel = {"error": str(e)[:120]}
        return {"mode": "nightly", "cycles": run["cycles"], "stopped": run["stopped"],
                "products": product, "intel": intel}

    def _learn(self, context, outcome="done"):
        """ذاكرة المهارات (مقترح كلاودي #2): تتعلّم من كل مهمة — نجاحاً وفشلاً — بلا توقف."""
        try:
            from agent_os import skill_memory
            skill_memory.remember(context, action=f"nucleus:{outcome}",
                                  ok=outcome in ("done", "approved"))
        except Exception:
            pass

    def _learn_cycle_web(self):
        """صيد المعرفة الخارجية (github/gitlab معروف) وسيتبلها في ذاكرة المهارات.
        - مرة واحدة في اليوم (علامة learning_day) — لا نزحف كلاسيكياً.
        - كل مصدر معزول بأخطاء صامتة: لا شيء يوقف الدورة.
        - تحت RETAGENT_OS_WEB_LEARN (افتراضي: مفعّل)."""
        if os.getenv("AGENT_OS_WEB_LEARN", "1") != "1":
            return []
        try:
            marker = os.path.join(C.AGENT_OS_DIR, "learning_day.json")
            if C.load_json(marker, {"day": ""}).get("day") == datetime.date.today().isoformat():
                return []
        except Exception:
            pass
        learned = []
        feeds = []
        try:
            feeds.append(_hunt_github("python automation"))
            feeds.append(_hunt_github("ai agents"))
            feeds.append(_hunt_gitlab())
        except Exception:
            pass
        for res in feeds:
            if not isinstance(res, dict):
                continue
            ok = res.get("ok")
            if ok:
                src = str(res.get("learned_from") or res.get("name") or res.get("topic") or "معرفة")
                learned.append(src[:40])
        try:
            C.atomic_write(marker, {"day": datetime.date.today().isoformat(),
                                    "learned": len(learned), "at": C.now_iso()})
        except Exception:
            pass
        if learned:
            C.log(f"📚 سلسلة التعلم الخارجي: تسجيلات جديدة في ذاكرة المهارات → {len(learned)}")
        return learned

    def _heartbeat_read(self):
        """طريقة القراءة عبر المثيل — تفويض للدالة العامة."""
        return read_heartbeat()

    def _health_check(self):
        """فحص صحّة قبل التشغيل (عيب 30): ملفات البيانات + مزود واحد على الأقل + مساحة قرص."""
        issues = []
        for name, path in (
            ("مالية", self.finance.FINANCE_FILE),
            ("أهداف", self.goals.GOALS_FILE),
            ("موافقات", self.approvals.REQUESTS_FILE),
        ):
            try:
                if not os.path.exists(path):
                    issues.append(f"ملف {name} غير موجود ({path})")
            except Exception as e:
                issues.append(f"ملف {name}: {e}")
        try:
            providers = self._get("brain").list_providers() if hasattr(self._get("brain"), "list_providers") else []
            if not providers:
                issues.append("لا مزوّدات مُهيّأة (تحقق من .env)")
        except Exception:
            pass
        try:
            import ctypes
            free = ctypes.c_ulonglong(0)
            root = os.path.splitdrive(C.BASE_DIR)[0] + "\\"
            if ctypes.windll.kernel32.GetDiskFreeSpaceExW(root, None, None, ctypes.byref(free)):
                if free.value and free.value < 500 * 1024 * 1024:
                    issues.append("مساحة قرص أقل من 500MB")
        except Exception:
            pass
        if issues:
            msg = "؛ ".join(issues)
            C.log(f"🚨 فحص صحّة فشل: {msg}")
            self._notify("critical", "فحص صحّة فشل", msg)
            return issues
        C.log("✅ فحص صحّة سليم")
        return []

    def _notify(self, level, title, message):
        """إخطار خارجي للأمور الحرجة عبر notifier (ملف JSON افتراضياً)."""
        try:
            from agent_os import notifier
            notifier.notify(level=level, title=title, message=message)
        except Exception:
            try:
                nt = os.path.join(C.AGENT_OS_DIR, "notifications.json")
                data = C.load_json(nt, {"items": []})
                data["items"].append({"level": level, "title": title[:120],
                                      "message": message[:500], "time": C.now_iso()})
                data["items"] = data["items"][-200:]
                C.atomic_write(nt, data)
            except Exception:
                pass

    def run_cycle(self, max_steps=6, allow_self_improve=False):
        """دورة حياة واحدة كاملة — تعيد ملخص ما فُعل هذه الدورة.
        allow_self_improve: يُفعَّل فقط في الجلسة المستمرة (run_until/run_loop)،
        حتى لا تلوّث دورة واحدة أو اختبار ملفات النواة المتحركة."""
        done = []

        self._heartbeat()

        # 0) المشرف: متابعة، تباطؤ، برودتنز، أو توقف بمؤشر حرِج (أمان بلا شلل)
        try:
            verdict = supervisor.check()
            self._supervisor_verdict = verdict
            if verdict["action"] == "stop":
                done.append(("supervisor_stop", verdict["reasons"]))
                return done  # حلقة توقفت بأمان
            if verdict["action"] == "cooldown":
                allow_self_improve = False
            if verdict["action"] == "slow":
                max_steps = min(max_steps, 3)
        except Exception as e:
            C.log(f"⚠️ مشرف لم يفحص: {e}")

        # 1) المالية أولاً: متى يمكننا الإنفاق؟
        fin = self.finance.daily_report()
        done.append(("finance", fin))

        # 2) الطلبات المعلقة — للإنسان أم لنا؟
        pending = self.approvals.pending_count()
        done.append(("pending_approvals", pending))

        # 2.5) إن وافقت على تعديلات حرجة — طبقها الآن (إكمال حلقة الإنسان)
        try:
            applied = self.self_improve.resolve_pending_critical_patches()
            if applied:
                done.append(("approved_patches_applied", [a["status"] for a in applied]))
        except Exception as e:
            C.log(f"⚠️ لم تُطبق التعديلات المدوّبة: {e}")

        # 3) ضمان أهداف
        for gid in self.ensure_goals():
            done.append(("goal_created", gid))
            try:
                event_bus.publish("goal_created", {"goal_id": gid, "source": "kernel"})
            except Exception:
                pass

        # 3.5) مهمة ذاتية من المولّد — مهمة واحدة فقط في اليوم، فقط حين يكون الطابور راكداً
        try:
            mission_marker = os.path.join(C.AGENT_OS_DIR, "mission_day.json")
            today = datetime.date.today().isoformat()
            marked = C.load_json(mission_marker, {"day": ""})
            if marked.get("day") != today and pending == 0:
                mission = mission_generator.next_mission()
                if mission:
                    self.goals.add_goal(mission["title"], objective=f"mission#{mission['id']}: {mission['reason']}",
                                        priority="medium", auto=False, category="mission")
                    C.atomic_write(mission_marker, {"day": today})
                    done.append(("mission_goal", mission["id"]))
        except Exception as e:
            C.log(f"⚠️ مهمة ذاتية لم تُستهلك: {e}")

        # 4) تنفيذ أهم مهمة جاهزة (يتخطى ما ينتظر موافقة)
        executed = 0
        while executed < max_steps:
            goal, task = self.goals.next_actionable_task()
            if not goal or not task:
                break
            # بوابة مالية: مهمة مدفوعة تتطلب رصيداً مكتسباً ضمن السقف اليومي
            if task.get("requires_paid"):
                if fin["self_earned_usd"] <= 0.0 or fin["budget_remaining_today"] <= 0.0:
                    C.log("💤 مهمة مدفوعة تنتظر رصيداً مكتسباً — تخطٍ.")
                    break
            res = self.nucleus.run_task(task["task"] + _skill_hint(task["task"]),
                                        why=task.get("result", ""),
                                        use_brain=self.use_brain)
            status = res["result"]["status"]
            if status in ("verified", "revised", "done", "approved"):
                self.goals.mark_done(task["id"], str(res["result"].get("output", ""))[:300])
                self._learn(task["task"], status)
            elif status == "needs_human":
                break  # اصعد للإنسان وتوقف الحلقة — لا نضحك على المهمة
            else:
                self.goals.mark_failed(task["id"], f"النواة: {status}")
                self._learn(task["task"], status)
            executed += 1
            done.append(("executed", task["task"][:60]))

        # 5) تحسين ذاتي كل 5 دورات — فقط في الجلسة المستمرة
        cy = C.load_json(CYCLE_FILE, {"count": 0})
        cy["count"] = cy.get("count", 0) + 1
        C.atomic_write(CYCLE_FILE, cy)
        if allow_self_improve and cy["count"] % 5 == 0:
            try:
                self.self_improve.run_improvement_cycle()
                done.append(("self_improve", "cycle"))
            except Exception as e:
                C.log(f"⚠️ دورة تحسين لم تكتمل: {e}")

        # 5.5) سلسلة التعلم الخارجي (مرة يومياً): معرفة github/gitlab → ذاكرة المهارات
        try:
            learned = self._learn_cycle_web()
            if learned:
                done.append(("web_learn", learned))
        except Exception as e:
            C.log(f"⚠️ صيد معرفة خارجي لم يكتمل: {e}")

        # 6) أرشفة برد بلا حذف: تُنقل القديمة لملفات مضغوطة، كل البيانات تُصان
        try:
            archived = self.finance.archive_old_records()
            if archived.get("moved"):
                done.append(("finance_archived", archived))
        except Exception as e:
            C.log(f"⚠️ أرشفة مالية لم تكتمل: {e}")
        try:
            garchived = self.goals.archive_achieved_goals()
            if garchived.get("moved"):
                done.append(("goals_archived", garchived))
        except Exception as e:
            C.log(f"⚠️ أرشفة أهداف لم تكتمل: {e}")

        return done

    # ===== جلسة مستمرة بمهلة آمنة =====

    def run_until(self, minutes=1.0, max_steps=6, allow_self_improve=True):
        """شغّل الحلقة حتى انقضاء المدة (كسر بطيء آمن) — ثم عُد بملخص."""
        deadline = time.time() + (minutes * 60)
        cycles = 0
        while time.time() < deadline:
            try:
                self.run_cycle(max_steps=max_steps, allow_self_improve=allow_self_improve)
            except Exception as e:
                C.log(f"⚠️ خلل دورة: {e}")
            cycles += 1
            time.sleep(3)
        return {"cycles": cycles, "stopped": C.now_iso()}


def is_night(hour=None, start=22, end=6):
    """وضع ليلي (مقترح كلاودي #8): ليل التقويم الافتراضي 22:00→06:00."""
    if hour is None:
        hour = int(datetime.datetime.now().strftime("%H"))
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def read_heartbeat():
    """آخر نبضة (يستعملها dashboard/watchdog قبل فتح الملف)."""
    return C.load_json(HEARTBEAT_FILE, {"ts": 0, "at": None, "pid": None})


def _hunt_github(query, n=5):
    """يستنتج مهارة عملية من GitHub العام ويسجّلها في ذاكرة المهارات (learn تخزّن بنفسها)."""
    try:
        from agent_os import github_hunter
        return github_hunter.learn(query, per_page=n)
    except Exception:
        return {"ok": False, "reason": "github_unavailable"}


def _hunt_gitlab(n=4):
    """يجلب معرفة حديثة من GitLab العام (مستودعات تعليمية)."""
    try:
        from agent_os import gitlab_hunter
        return gitlab_hunter.recent(n)
    except Exception:
        return []


def run_nightly(minutes=55.0, allow_self_improve=True, use_brain=True):
    """CLI: وضع ليلي — استمرارية + تحسين ذاتي + خط إنتاج ليلي.
    العقل الهجين مفعّل افتراضياً في الاستدعاء الصريح (نقد المقيّم: النواة كانت بلا دماغ)."""
    agent = AgentOS(use_brain=use_brain)
    return agent.run_nightly(minutes, allow_self_improve=allow_self_improve)


def _skill_hint(task_text):
    """حقن المهارات المكتسبة في كل مهمة (نقد المقيّم: «مهارات لا تُحقن في كل مهمة»).
    يستحضر الأقرب من skills.mem ويُلحقها سياقاً — بلا شبكة وبلا مقاومة للفشل."""
    try:
        from agent_os import skill_memory
        hits = skill_memory.recall(task_text, top=3)
        if not hits:
            return ""
        lines = [h["parts"][1][:120] + " ← " + h["parts"][2][:120] for h in hits
                 if len(h.get("parts", [])) >= 3]
        return "\n[مهارات من ذاكرة المهام السابقة]\n" + "\n".join(lines) + "\n"
    except Exception:
        return ""


def run_loop(minutes=1.0, use_brain=False):
    """CLI: شغّل نواة التشغيل المستمر لمدة محددة.
    يفحص الصحّة أولاً (عيب 30): إن فشل يكتب تنبيهاً ويتوقف بدل تشغيل حالة فاسدة.
    العقل الهجين يُفعل صراحةً (CLI/employ — نقد المقيّم)، وليس افتراضياً للمكتبة."""
    agent = AgentOS(use_brain=use_brain)
    issues = agent._health_check()
    if issues and minutes > 0:
        return {"cycle": None, "health_issues": issues, "stopped": "health_failed"}
    if minutes <= 0:
        # جولة واحدة ثم نهاية هادئة
        return {"cycle": agent.run_cycle(), "mode": "single"}
    result = agent.run_until(minutes)
    C.log(f"🛑 توقفت بعد {result['cycles']} دورات.")
    return result


if __name__ == "__main__":
    import json
    if len(sys.argv) > 1 and sys.argv[1] == "nightly":
        minutes = float(sys.argv[2]) if len(sys.argv) > 2 else 55.0
        res = run_nightly(minutes, allow_self_improve=True, use_brain=True)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "isnight":
        print(json.dumps(is_night()))
    else:
        amt = float(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] not in ("once", "nightly") else 0
        res = run_loop(amt, use_brain=True) if amt != 0 else run_loop(0, use_brain=True)
        print(json.dumps(res, ensure_ascii=False, indent=1))