"""Public GitLab knowledge hunter.
Only reads public metadata/README through the central network policy. It does
not clone repositories or bypass authentication. Use it to discover techniques
and then validate licenses before reusing code.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent_os import _common as C

FILE=os.path.join(C.AGENT_OS_DIR,"gitlab_hunts.json")
ALLOWED_LICENSES={"MIT","Apache-2.0","BSD-2-Clause","BSD-3-Clause","ISC","MPL-2.0","LGPL-3.0","GPL-3.0"}

def _api(url):
    try:
        import webtools
        body=webtools._fetch(url,timeout=15)
        return json.loads(body) if isinstance(body,str) and body.lstrip().startswith(("{","[")) else None
    except Exception:return None

def hunt(query, per_page=10):
    from urllib.parse import quote_plus
    url=f"https://gitlab.com/api/v4/projects?search={quote_plus(query)}&order_by=star_count&sort=desc&per_page={min(max(per_page,1),20)}"
    rows=_api(url)
    if not isinstance(rows,list): return {"query":query,"error":"لا استجابة من GitLab"}
    items=[]
    for p in rows:
        license_name=((p.get("license") or {}).get("key") or (p.get("license") or {}).get("name") or "")
        items.append({"id":p.get("id"),"path":p.get("path_with_namespace",""),"url":p.get("web_url",""),"stars":p.get("star_count",0),"license":license_name,"language":p.get("programming_language","")})
    rec={"query":query,"time":C.now_iso(),"items":items}
    st=C.load_json(FILE,{"hunts":[]}); st["hunts"].append(rec); C.atomic_write(FILE,st)
    return rec

def recent(n=10): return C.load_json(FILE,{"hunts":[]})["hunts"][-n:]
