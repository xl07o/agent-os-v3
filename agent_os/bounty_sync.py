"""
bounty_sync.py - جالب برامج المكافآت العامة (v1.0)
====================================================
مصدر الشرعية: تفويض برامج bounty العامة عبر سياسة المنصة العلنية (TOS)،
وليس أي مسح عشوائي لأي مضيف. النطاق يُقفَل حصراً من بيانات البرنامج المعلنة.

المصادر: بيانات المكافآت العامة للمنصات:
  hackerone | bugcrowd | intigriti | yeswehack | federacy | immunefi

الاستخدام:
  python agent_os/bounty_sync.py list <platform> [N]
  python agent_os/bounty_sync.py adopt <platform> <index>
  python agent_os/bounty_sync.py candidates [N]
  python agent_os/bounty_sync.py refresh <platform>
"""

import os
import re
import sys
import time
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C
from agent_os import bounty_engine

FEEDS = {
    "hackerone": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/master/data/hackerone_data.json",
    "bugcrowd": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/master/data/bugcrowd_data.json",
    "intigriti": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/master/data/intigriti_data.json",
    "yeswehack": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/master/data/yeswehack_data.json",
    "federacy": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/master/data/federacy_data.json",
    "immunefi": "https://raw.githubusercontent.com/infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial/main/projects.json",
}

CACHE_DIR = os.path.join(C.AGENT_OS_DIR, "bounty_sync")
MAX_AGE_SECONDS = 24 * 3600
_UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# صيغ نطاق مقبولة للاعتماد: URL كامل أو اسم مضيف صالح (بلا نجوم نطاقات عشوائية)
_HOST_RE = re.compile(
    r"^(https?://[a-z0-9.\-]+(?:/[^\s]*)?|[a-z0-9](?:[a-z0-9\-.]*[a-z0-9])?\.[a-z]{2,}(?:/[^\s]*)?)$",
    re.I,
)


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def fetch_public(platform, refresh=False, timeout=90):
    """جلب بيانات المنصة مع كاش محلي (24 ساعة) — لا إعادة تنزيل مكلفة في كل مرة."""
    platform = (platform or "").lower()
    if platform not in FEEDS:
        raise ValueError(f"منصة غير معروفة: {platform} (المتاحة: {', '.join(FEEDS)})")
    cache = os.path.join(CACHE_DIR, f"{platform}.json")
    if not refresh and os.path.exists(cache):
        try:
            if time.time() - os.path.getmtime(cache) < MAX_AGE_SECONDS:
                with open(cache, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    data = _get(FEEDS[platform], timeout=timeout)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        C.atomic_write(cache, data)
    except Exception:
        pass
    return data


def _target_id(t):
    for k in ("target", "uri", "asset_identifier", "identifier", "scope", "data", "url", "endpoint"):
        v = t.get(k)
        if v:
            return str(v).strip()
    return str(t.get("name") or "").strip()


def _target_type(t):
    return str(t.get("type") or t.get("asset_type") or t.get("name") or "")[:24]


def _meta_of(platform, rec):
    """استخراج هوية ومكافأة البرنامج حسب شكل بيانات كل منصة."""
    p = platform
    if p == "yeswehack":
        return {"name": (rec.get("name") or "?").strip(),
                "url": rec.get("url") or f"https://yeswehack.com/programs/{rec.get('id') or ''}",
                "pay": rec.get("max_bounty") or 0,
                "offers": bool(rec.get("min_bounty") or rec.get("max_bounty"))}
    if p == "federacy":
        return {"name": (rec.get("name") or "?").strip(),
                "url": rec.get("url") or "",
                "pay": 0,
                "offers": bool(rec.get("offers_awards"))}
    if p == "immunefi":
        return {"name": (rec.get("project") or rec.get("slug") or "?").strip(),
                "url": f"https://immunefi.com/bug-bounty/{rec.get('slug') or ''}",
                "pay": rec.get("maxBounty") or 0,
                "offers": True}
    if p == "intigriti":
        _mb = rec.get("max_bounty") or {}
        _mn = rec.get("min_bounty") or {}
        _val = lambda x: x.get("value") if isinstance(x, dict) else (x or 0)
        return {"name": (rec.get("name") or rec.get("handle") or "?").strip(),
                "url": rec.get("url") or "",
                "pay": _val(_mb),
                "offers": bool(_val(_mb) or _val(_mn))}
    return {"name": (rec.get("name") or rec.get("handle") or "?").strip(),
            "url": rec.get("url") or "",
            "pay": rec.get("max_payout"),
            "offers": rec.get("offers_bounties")}


def _targets_of(platform, rec):
    """نطاقات البرنامج الداخل: لكل منصة شكلها، مع فلترة الصيغ غير القابلة للفحص.
    منصة Immunefi نطاقاتها عقود وBlockchain ومواقع — نحتفظ بها كلها (لا نتخلص
    من عناوين العقود)، أما غيرها فيفلتر النجوم العشوائية و IP CIDRs."""
    out = []
    seen = set()
    if platform == "immunefi":
        for a in rec.get("assets") or []:
            tid = a.get("url") or a.get("id") or a.get("name")
            if tid:
                tid = str(tid).strip()
                if tid and tid not in seen:
                    seen.add(tid)
                    out.append((tid, str(a.get("type") or "smart_contract")[:24]))
        return out
    for t in (rec.get("targets") or {}).get("in_scope") or []:
        tid = _target_id(t)
        ttype = _target_type(t).lower()
        if ttype in {"ios", "android", "windows", "macos", "linux"}:
            continue
        if not tid or tid.lower() in ("*", "none", "-") or tid in seen:
            continue
        if not _HOST_RE.match(tid):
            continue
        seen.add(tid)
        out.append((tid, _target_type(t)))
    return out


def normalize_record(platform, rec):
    """تطبيع سجل منصة إلى عقدة موحّدة: اسم + رابط + نطاقات الداخل (ids فقط)."""
    meta = _meta_of(platform, rec)
    targets = _targets_of(platform, rec)
    if not targets:
        return None
    return {
        "platform": platform,
        "name": meta["name"],
        "url": meta["url"],
        "max_payout": meta.get("pay"),
        "offers_bounties": meta.get("offers"),
        "safe_harbor": rec.get("safe_harbor"),
        "n_targets": len(targets),
        "targets": targets,
    }


def candidates(platforms=None, cap=3000):
    """كل البرامج المرشحة عبر المنصات، مرتبة تنازلياً بأعلى مكافأة، مع الاقتصار
    على البرامج العارضة لمكافأة (تركيز الطريق نحو الدخل لا "العمل المجاني" فقط)."""
    platforms = [p for p in (platforms or list(FEEDS)) if p in FEEDS]
    res = []
    for p in platforms:
        for rec in fetch_public(p):
            r = normalize_record(p, rec)
            if r and (r["offers_bounties"] or (r.get("max_payout") or 0) > 0):
                res.append(r)
    res.sort(key=lambda r: -(r.get("max_payout") or 0))
    return res[:cap]


def adopt(platform, index, cap_targets=300):
    """اعتماد برنامج محلّي: يقفل نطاقه المعلن ويوثّق مصدر التفويض كسياسية المنصة.
    يرجع البرنامج المُنشأ أو {'status':'dup'} إن كان موجوداً."""
    cands = candidates([platform], cap=5000)
    if not 0 <= index < len(cands):
        return {"status": "error", "reason": "الفهرس خارج الحدود"}
    rec = cands[index]
    for p in bounty_engine.list_programs():
        if p.get("name") == rec["name"]:
            return {"status": "dup", "name": rec["name"], "program_id": p.get("id")}
    ids = [tid for tid, _ in rec["targets"][:cap_targets]]
    rules = (
        f"سياسية {rec['platform'].upper()} العلنية لبرامج المكافآت هي التفويض. "
        "ممنوع: إجراءات تخريبية أو حذف أو DoS/Phish ، تجاوز النطاق المعلن، "
        "بيانات مستخدمين حقيقية. ابدأ فحصاً سلبياً أولاً، ثم نشطاً منخفض الأثر داخل النطاق فقط. "
        f"البرنامج: {rec['url']}"
    )
    prog = bounty_engine.add_program(
        rec["name"], ids, rules=rules,
        authorization_source=f"public-policy:{rec['platform']}",
    )
    prog["source_url"] = rec.get("url")
    C.log(f"🛡️ اعتماد برنامج #{prog['id']}: {rec['name']} ({rec['platform']}) — {len(ids)} نطاقاً")
    return prog


def selftest():
    """فحص ذاتي بلا شبكة: تطبيع أشكال بيانات المنصات من عيّنات حرفية."""
    sample_bc = {
        "name": "Sample BC", "url": "https://bugcrowd.com/engagements/x",
        "max_payout": 7500, "safe_harbor": "full", "targets": {
            "in_scope": [{"type": "api", "target": "https://api.example.com/"}],
            "out_of_scope": [{"type": "website", "target": "https://www.example.com/"}],
        }}
    sample_h1 = {
        "name": "Sample H1", "handle": "x", "url": "https://hackerone.com/x",
        "offers_bounties": True, "targets": {
            "in_scope": [{"asset_identifier": "app.example.com", "asset_type": "URL"},
                         {"asset_identifier": "*.wild.example.com", "asset_type": "URL"}],
        }}
    sample_int = {
        "name": "Adobe", "url": "https://www.intigriti.com/programs/adobe/x",
        "min_bounty": {"value": 75, "currency": "USD"},
        "max_bounty": {"value": 15000, "currency": "USD"},
        "targets": {"in_scope": [{"target": "https://a.example.com/", "type": "website"}]}}
    sample_ywh = {
        "id": "acme", "name": "Acme", "max_bounty": 5000,
        "targets": {"in_scope": [{"target": "https://acme.example.com/", "type": "api"}]}}
    sample_imm = {
        "project": "Acme DAO", "slug": "acme-dao", "maxBounty": 250000,
        "assets": [{"url": "https://app.acme-dao.example/", "type": "websites_and_applications"},
                   {"url": "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B", "type": "smart_contract"}]}
    r1 = normalize_record("bugcrowd", sample_bc)
    r2 = normalize_record("hackerone", sample_h1)
    r3 = normalize_record("intigriti", sample_int)
    r4 = normalize_record("yeswehack", sample_ywh)
    r5 = normalize_record("immunefi", sample_imm)
    ok1 = r1 and r1["targets"] == [("https://api.example.com/", "api")]
    ok2 = r2 and r2["n_targets"] == 1 and all("*" not in t[0] for t in r2["targets"])
    ok3 = r3 and r3["max_payout"] == 15000 and r3["offers_bounties"] is True
    ok4 = r4 and r4["max_payout"] == 5000 and r4["url"].startswith("https://yeswehack.com/")
    ok5 = r5 and r5["max_payout"] == 250000 and r5["n_targets"] == 2 and r5["offers_bounties"] is True
    return {"parser_bugcrowd": ok1, "parser_hackerone": ok2, "parser_intigriti": ok3,
            "parser_yeswehack": ok4, "parser_immunefi": ok5,
            "all": bool(ok1 and ok2 and ok3 and ok4 and ok5)}


def _fmt_candidate(i, r):
    pay = r.get("max_payout") or 0
    return (f"[{i}] {r['name']} | ${pay:,} | {r['n_targets']} نطاقاً | bounty=Y "
            f"| {r['url']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "candidates"
    if cmd == "selftest":
        print("selftest:", selftest())
    elif cmd == "candidates":
        n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
        for i, r in enumerate(candidates()[:n]):
            print(_fmt_candidate(i, r))
    elif cmd in ("list",) and len(args) >= 2:
        platform = args[1]
        n = int(args[2]) if len(args) > 2 and args[2].isdigit() else 10
        for i, r in enumerate(candidates([platform])[:n]):
            print(_fmt_candidate(i, r))
    elif cmd == "adopt" and len(args) >= 3:
        print(adopt(args[1], int(args[2])))
    elif cmd == "plan" and len(args) >= 3:
        prog = adopt(args[1], int(args[2]))
        if isinstance(prog, dict) and prog.get("program_id") is not None:
            prog_id = prog["program_id"]
        else:
            prog_id = prog.get("id")
        print(bounty_engine.attack_plan(prog_id))
    elif cmd == "refresh" and len(args) >= 2:
        fetch_public(args[1], refresh=True)
        print(f"أُعيد جلبه: {args[1]}")
    else:
        print(__doc__)