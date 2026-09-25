"""
intent_engine.py - محرك فهم النية (Intent Engine)
==================================================
يحول كلام المستخدم إلى نية قابلة للتنفيذ.

مثال:
  "ابنِ لي موقع" -> {intent: build, type: website, priority: high}
  "ابحث عن فرص" -> {intent: research, type: opportunities, priority: medium}
  "تعلم Python" -> {intent: learn, topic: python, priority: medium}
"""

import re

# خريطة النوايا
INTENT_MAP = {
    "build": {
        "keywords": ["ابنِ", "ابني", "اصنع", "اعمل", "انشئ", "أنشئ", "build", "create", "make"],
        "subtypes": {
            "website": ["موقع", "ويب", "web", "site", "landing"],
            "app": ["تطبيق", "app", "application", "mobile"],
            "api": ["api", "واجهة", "endpoint"],
            "script": ["سكريبت", "script", "أداة", "tool"],
            "saas": ["saas", "خدمة", "service", "منتج", "product"],
        }
    },
    "research": {
        "keywords": ["ابحث", "بحث", "اكتشف", "اعثر", "search", "find", "research", "explore"],
        "subtypes": {
            "opportunities": ["فرص", "فرصة", "opportunity", "opportunities"],
            "tools": ["أدوات", "tool", "tools", "api"],
            "information": ["معلومات", "info", "information", "about"],
        }
    },
    "learn": {
        "keywords": ["تعلم", "تعلّم", "ادرس", "learn", "study", "understand"],
        "subtypes": {}
    },
    "improve": {
        "keywords": ["حسّن", "طور", "improve", "optimize", "enhance", "upgrade"],
        "subtypes": {
            "self": ["نفسك", "نفسي", "yourself", "self"],
            "code": ["كود", "code", "برمجة"],
            "performance": ["أداء", "performance", "speed"],
        }
    },
    "deploy": {
        "keywords": ["انشر", "نشر", "deploy", "publish", "launch", "release"],
        "subtypes": {}
    },
    "analyze": {
        "keywords": ["حلل", "تحليل", "analyze", "analyse", "review", "audit"],
        "subtypes": {}
    },
    "fix": {
        "keywords": ["أصلح", "صلح", "fix", "repair", "debug", "solve"],
        "subtypes": {}
    },
    "report": {
        "keywords": ["تقرير", "ملخص", "report", "summary", "brief"],
        "subtypes": {}
    },
    "monitor": {
        "keywords": ["راقب", "مراقبة", "monitor", "watch", "track"],
        "subtypes": {}
    },
    "earn": {
        "keywords": ["دخل", "ربح", "فلوس", "مال", "earn", "revenue", "money", "income"],
        "subtypes": {}
    },
}

# مستويات الأولوية
URGENCY_KEYWORDS = {
    "critical": ["الآن", "فوراً", "عاجل", "urgent", "immediately", "asap", "critical"],
    "high": ["اليوم", "سريع", "today", "soon", "quickly", "fast"],
    "medium": ["هذا الأسبوع", "this week", "when possible"],
    "low": ["لاحقاً", "later", "eventually", "someday"],
}


class IntentEngine:
    """يفهم النية الحقيقية وراء طلب المستخدم."""

    def parse(self, text: str) -> dict:
        """
        يحلل النص ويستخرج النية.

        يرجع:
          intent: النية الرئيسية
          subtype: النوع الفرعي
          urgency: مستوى الإلحاح
          entities: الكيانات المستخرجة
          confidence: مستوى الثقة
          raw_goal: الهدف الخام
        """
        text_lower = text.lower()

        # استخراج النية
        intent = "general"
        subtype = None
        confidence = 0.5

        for intent_name, intent_data in INTENT_MAP.items():
            for keyword in intent_data["keywords"]:
                if keyword.lower() in text_lower:
                    intent = intent_name
                    confidence = 0.8

                    # استخراج النوع الفرعي
                    for sub_name, sub_keywords in intent_data.get("subtypes", {}).items():
                        for sub_kw in sub_keywords:
                            if sub_kw.lower() in text_lower:
                                subtype = sub_name
                                confidence = 0.9
                                break
                        if subtype:
                            break
                    break
            if intent != "general":
                break

        # استخراج الإلحاح
        urgency = "medium"
        for level, keywords in URGENCY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    urgency = level
                    break

        # استخراج الكيانات (أسماء، تقنيات، إلخ)
        entities = self._extract_entities(text)

        return {
            "intent": intent,
            "subtype": subtype,
            "urgency": urgency,
            "entities": entities,
            "confidence": confidence,
            "raw_goal": text,
            "executable": intent != "general",
        }

    def _extract_entities(self, text: str) -> list:
        """يستخرج الكيانات من النص."""
        entities = []

        # تقنيات شائعة
        tech_patterns = [
            r"\b(python|javascript|typescript|react|vue|angular|node|fastapi|flask|django)\b",
            r"\b(docker|kubernetes|aws|azure|gcp|heroku|vercel|netlify)\b",
            r"\b(postgresql|mysql|mongodb|redis|sqlite)\b",
            r"\b(github|gitlab|git)\b",
            r"\b(api|rest|graphql|websocket|grpc)\b",
        ]

        for pattern in tech_patterns:
            matches = re.findall(pattern, text.lower())
            entities.extend(matches)

        return list(set(entities))

    def to_goal(self, parsed: dict) -> dict:
        """
        يحول النية المحللة إلى Goal قابل للتنفيذ.
        """
        intent = parsed["intent"]
        subtype = parsed.get("subtype", "")
        entities = parsed.get("entities", [])
        raw = parsed.get("raw_goal", "")

        # بناء عنوان الهدف
        title = raw[:80]
        if intent == "build" and subtype:
            title = f"بناء {subtype}: {raw[:60]}"
        elif intent == "research":
            title = f"بحث: {raw[:60]}"
        elif intent == "learn":
            title = f"تعلم: {raw[:60]}"
        elif intent == "earn":
            title = f"إيجاد مصدر دخل: {raw[:60]}"

        return {
            "title": title,
            "intent": intent,
            "subtype": subtype,
            "entities": entities,
            "urgency": parsed.get("urgency", "medium"),
            "confidence": parsed.get("confidence", 0.5),
            "raw": raw,
            "priority": self._urgency_to_priority(parsed.get("urgency", "medium")),
        }

    def _urgency_to_priority(self, urgency: str) -> int:
        """يحول الإلحاح لرقم أولوية (1=أعلى)."""
        mapping = {"critical": 1, "high": 2, "medium": 5, "low": 8}
        return mapping.get(urgency, 5)


# Singleton
_engine = IntentEngine()


def parse_intent(text: str) -> dict:
    return _engine.parse(text)


def text_to_goal(text: str) -> dict:
    parsed = _engine.parse(text)
    return _engine.to_goal(parsed)


if __name__ == "__main__":
    tests = [
        "ابنِ لي موقع ويب بـ Python",
        "ابحث عن فرص دخل",
        "تعلم Docker",
        "حسّن أداء النظام",
        "ابحث عن API مجانية",
    ]
    import json
    for t in tests:
        result = parse_intent(t)
        print(f"\n'{t}'")
        print(f"  intent={result['intent']}, subtype={result['subtype']}, urgency={result['urgency']}")
