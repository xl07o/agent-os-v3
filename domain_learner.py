"""
domain_learner.py — نظام التعلم العميق قبل التنفيذ
=====================================================
قبل أي تنفيذ حقيقي في أي مجال، الوكيل يتعلم، يحلل، يجرب ويبني
خبرة حقيقية. لا ينفذ حتى يثبت للنفسه أنه جاهز.

مثال تداول: يتعلم الرسوم البيانية، يحلل الأسهم، يسوي تجارب
تجريبية، ويوم استراتيجيته تنجح — يبدأ يتداول فعلياً.
"""

from __future__ import annotations
import json
import os
import time
import threading
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
_KNOWLEDGE_DIR = _HERE / "memory" / "domains"
_KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


class DomainKnowledge:
    """حالة المعرفة لمجال معين."""

    def __init__(self, domain: str):
        self.domain = domain
        self._path = _KNOWLEDGE_DIR / f"{domain.replace(' ', '_')}.json"
        self._data = self._load()

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "domain": self.domain,
                "level": 0,
                "lessons": [],
                "simulations": [],
                "success_rate": 0.0,
                "ready_threshold": 70,
                "last_updated": None,
            }

    def save(self):
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)

    @property
    def level(self) -> int:
        return self._data.get("level", 0)

    @level.setter
    def level(self, v: int):
        self._data["level"] = max(0, min(100, int(v)))
        self._data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save()

    @property
    def ready(self) -> bool:
        return self.level >= self._data.get("ready_threshold", 70)

    def add_lesson(self, lesson: str, source: str = "web"):
        self._data["lessons"].append({
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "lesson": lesson[:500],
            "source": source,
        })
        self._data["level"] = min(100, self._data["level"] + 3)
        self.save()

    def add_simulation(self, task: str, result: str, success: bool):
        sims = self._data.setdefault("simulations", [])
        sims.append({
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "task": task[:200],
            "result": result[:500],
            "success": success,
        })
        successes = sum(1 for s in sims if s.get("success"))
        self._data["success_rate"] = round(successes / len(sims), 2)
        if success:
            self._data["level"] = min(100, self._data["level"] + 5)
        self.save()

    def summary(self) -> str:
        d = self._data
        return (
            f"مجال: {self.domain} | مستوى: {d['level']}% | "
            f"دروس: {len(d.get('lessons', []))} | "
            f"تجارب: {len(d.get('simulations', []))} | "
            f"نجاح: {d.get('success_rate', 0)*100:.0f}% | "
            f"{'✅ جاهز' if self.ready else '📚 يتعلم...'}"
        )


class DomainLearner:
    """
    وكيل التعلم العميق — يتعلم أي مجال قبل التنفيذ.

    الاستخدام:
        learner = DomainLearner("تداول الأسهم")
        learner.learn_until_ready("سوِّ 20 صفقة رابحة")
        # الآن يمكن التنفيذ الفعلي
    """

    def __init__(self, domain: str, brain_instance=None):
        self.domain = domain
        self.knowledge = DomainKnowledge(domain)
        self._brain = brain_instance
        self._lock = threading.Lock()

    def _get_brain(self):
        if self._brain:
            return self._brain
        try:
            import brain as _brain_mod
            return _brain_mod.Brain(
                f"أنت خبير في مجال '{self.domain}'. أجب بدقة وإيجاز بالعربية."
            )
        except Exception:
            return None

    def assess_knowledge(self) -> int:
        """يسأل العقل: كم تعرف عن هذا المجال؟ يرجع 0-100."""
        b = self._get_brain()
        if not b:
            return self.knowledge.level
        try:
            out, engine = b.ask(
                f"على مقياس من 0 إلى 100، كم تعرف الآن عن '{self.domain}'? "
                "ردّ برقم فقط."
            )
            if engine not in (None, "none"):
                import re
                nums = re.findall(r'\d+', str(out))
                if nums:
                    return min(100, max(0, int(nums[0])))
        except Exception:
            pass
        return self.knowledge.level

    def research_topic(self, topic: str) -> str:
        """يبحث ويتعلم موضوعاً محدداً في المجال."""
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(f"{topic} {self.domain}", max_results=3))
            lesson = f"بحث عن '{topic}':\n"
            for r in results:
                lesson += f"- {r.get('title', '')}: {r.get('body', '')[:200]}\n"
            self.knowledge.add_lesson(lesson, source="duckduckgo")
            return lesson
        except Exception as e:
            lesson = f"تعذّر البحث عن '{topic}': {e}"
            return lesson

    def simulate_task(self, task: str) -> tuple[bool, str]:
        """يجرب المهمة تجريبياً (بدون تنفيذ حقيقي) ويقيّم النتيجة."""
        b = self._get_brain()
        if not b:
            return False, "لا يوجد عقل متاح للتجريب"
        try:
            out, engine = b.ask(
                f"[وضع تجريبي — بدون تنفيذ حقيقي]\n"
                f"المجال: {self.domain}\n"
                f"المهمة: {task}\n\n"
                f"افترض أنك نفّذت هذه المهمة بناءً على معرفتك. "
                f"هل ستنجح؟ ولماذا؟ كن صريحاً. "
                f"ابدأ بـ 'نجح:' أو 'فشل:'"
            )
            if engine in (None, "none"):
                return False, "لا يوجد عقل متاح"
            success = str(out).strip().startswith("نجح")
            self.knowledge.add_simulation(task, str(out)[:400], success)
            return success, str(out)[:400]
        except Exception as e:
            return False, f"خطأ في التجريب: {e}"

    def learning_cycle(self, task: str, topics: Optional[list] = None) -> dict:
        """
        دورة تعلم واحدة:
        1. تقييم المعرفة الحالية
        2. بحث وتعلم
        3. تجربة تجريبية
        4. إرجاع الحالة
        """
        level_before = self.knowledge.level

        # تعلم من الويب
        research_topics = topics or [
            f"أساسيات {self.domain}",
            f"استراتيجيات {self.domain}",
            f"أخطاء شائعة في {self.domain}",
        ]
        for topic in research_topics[:2]:
            self.research_topic(topic)
            time.sleep(0.5)

        # تجريب
        success, result = self.simulate_task(task)

        level_after = self.knowledge.level
        return {
            "level_before": level_before,
            "level_after": level_after,
            "level_gain": level_after - level_before,
            "simulation_success": success,
            "simulation_result": result,
            "ready": self.knowledge.ready,
            "summary": self.knowledge.summary(),
        }

    def learn_until_ready(
        self,
        task: str,
        max_cycles: int = 10,
        progress_callback=None,
    ) -> dict:
        """
        يتعلم دورة بعد دورة حتى يصبح جاهزاً للتنفيذ الفعلي.

        الحد الأقصى max_cycles يمنع التكرار اللانهائي.
        يرجع dict بالحالة النهائية.
        """
        print(f"\n📚 بدء التعلم العميق لمجال: {self.domain}")
        print(f"   المهمة: {task}")
        print(f"   المستوى الحالي: {self.knowledge.level}%")

        for cycle in range(1, max_cycles + 1):
            if self.knowledge.ready:
                break

            print(f"\n   [دورة {cycle}/{max_cycles}] {self.knowledge.summary()}")

            result = self.learning_cycle(task)

            if progress_callback:
                progress_callback(cycle, result)

            if result["simulation_success"] and self.knowledge.level >= 60:
                # تقدم جيد — ارفع عتبة الجاهزية تدريجياً
                pass

        status = "جاهز للتنفيذ ✅" if self.knowledge.ready else "يحتاج مزيداً من التعلم 📚"
        print(f"\n   النتيجة النهائية: {status}")
        print(f"   المستوى: {self.knowledge.level}% | معدل النجاح: {self.knowledge._data.get('success_rate', 0)*100:.0f}%")

        return {
            "domain": self.domain,
            "task": task,
            "final_level": self.knowledge.level,
            "success_rate": self.knowledge._data.get("success_rate", 0),
            "lessons_count": len(self.knowledge._data.get("lessons", [])),
            "simulations_count": len(self.knowledge._data.get("simulations", [])),
            "ready": self.knowledge.ready,
            "status": status,
        }

    def status_report(self) -> str:
        return self.knowledge.summary()


# ===== قاموس المجالات المتاحة =====
DOMAIN_TOPICS = {
    "تداول الأسهم": [
        "تحليل فني أسهم", "مؤشرات RSI MACD", "إدارة المخاطر",
        "استراتيجيات التداول اليومي", "قراءة الشموع اليابانية",
    ],
    "تداول العملات المشفرة": [
        "بيتكوين تحليل فني", "استراتيجيات كريبتو",
        "DeFi أساسيات", "إدارة محفظة كريبتو",
    ],
    "البرمجة": [
        "Python متقدم", "خوارزميات وبنى بيانات",
        "تصميم أنظمة", "اختبار الكود",
    ],
    "التسويق الرقمي": [
        "SEO محركات بحث", "تسويق بالمحتوى",
        "إعلانات مدفوعة", "تحليل البيانات",
    ],
    "الأمن السيبراني": [
        "اختبار الاختراق", "تحليل الثغرات",
        "أمن الشبكات", "تشفير البيانات",
    ],
}


def get_domain_learner(domain: str) -> DomainLearner:
    """إنشاء DomainLearner مع Topics المناسبة للمجال."""
    learner = DomainLearner(domain)
    return learner


if __name__ == "__main__":
    import sys
    domain = sys.argv[1] if len(sys.argv) > 1 else "تداول الأسهم"
    task = sys.argv[2] if len(sys.argv) > 2 else "سوِّ 5 صفقات رابحة"
    learner = get_domain_learner(domain)
    print(learner.status_report())
    result = learner.learn_until_ready(task, max_cycles=3)
    print(json.dumps(result, ensure_ascii=False, indent=2))
