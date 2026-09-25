"""
chain_of_thought.py - التفكير المتسلسل العميق
===============================================
بدل سؤال واحد → سلسلة أسئلة مترابطة. كل جواب يبني السؤال التالي.
يوصل لاستنتاجات ما يقدر يوصلها بسؤال واحد.
"""
import os, sys
def _ensure_root_on_path():
    _d = os.path.dirname(os.path.abspath(__file__))
    while _d and not os.path.isfile(os.path.join(_d, "agent_os", "__init__.py")):
        _d = os.path.dirname(_d)
    if _d and _d not in sys.path:
        sys.path.insert(0, _d)

_ensure_root_on_path()
del _ensure_root_on_path
from agent_os import _common as C

MAX_STEPS = 5

def think_chain(question, steps=3, mode="smart"):
    """يفكر بسلسلة: سؤال → جواب → سؤال مبني عليه → ... → استنتاج نهائي."""
    steps = min(steps, MAX_STEPS)
    chain = []
    current_q = question
    accumulated = ""

    for i in range(steps):
        prompt = f"السياق المتراكم:\n{accumulated}\n\nالسؤال الحالي: {current_q}" if accumulated else current_q
        try:
            answer, engine = C.call_brain(
                "فكّر بعمق وأجب بإيجاز. في نهاية إجابتك اطرح سؤالاً تالياً يعمّق الفهم.",
                prompt, mode=mode)
            if not answer or answer.startswith("("):
                chain.append({"step": i+1, "question": current_q, "answer": None, "note": "لا مزوّد"})
                break
        except Exception as e:
            chain.append({"step": i+1, "question": current_q, "error": str(e)[:100]})
            break

        chain.append({"step": i+1, "question": current_q, "answer": answer[:600], "engine": engine})
        accumulated += f"\nخطوة {i+1}: {answer[:300]}"

        # استخرج السؤال التالي من نهاية الجواب
        lines = answer.strip().split("\n")
        last_line = lines[-1].strip()
        if "?" in last_line or "؟" in last_line:
            current_q = last_line
        else:
            current_q = f"بناءً على ما سبق، ما الاستنتاج النهائي؟"

    return {
        "original_question": question,
        "chain": chain,
        "depth": len(chain),
        "final_answer": chain[-1].get("answer") if chain else None,
    }

def quick_think(question):
    """تفكير سريع بخطوتين فقط."""
    return think_chain(question, steps=2)

def deep_think(question):
    """تفكير عميق بـ5 خطوات."""
    return think_chain(question, steps=5)
