# -*- coding: utf-8 -*-
"""أدوات نظام الملفات — عمليات حقيقية على القرص داخل جذر العمل."""
import fnmatch
import os
import re

from .. import config

def _bail(args, key, default=None):
    if not isinstance(args, dict):
        args = {}
    return args.get(key, default)

def read_file(args):
    path = config.safe_resolve(_bail(args, "path"))
    if not os.path.isfile(path):
        return {"ok": False, "error": "لا يوجد ملف: %s" % path}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = f.read(config.MAX_FILE_BYTES + 1)
    truncated = len(data) > config.MAX_FILE_BYTES
    return {"ok": True, "path": path, "size": len(data), "truncated": truncated,
            "content": data[:config.MAX_FILE_BYTES]}

def write_file(args):
    path = config.safe_resolve(_bail(args, "path"))
    content = _bail(args, "content") or ""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "path": path, "bytes": len(content.encode("utf-8")),
            "artifact": path, "note": "كتب الملف: %s" % path}

def edit_file(args):
    path = config.safe_resolve(_bail(args, "path"))
    old = _bail(args, "old")
    new = _bail(args, "new")
    if old is None or new is None:
        return {"ok": False, "error": "تحتاج old و new"}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = f.read()
    count = data.count(old)
    if count == 0:
        return {"ok": False, "error": "النص القديم غير موجود في الملف"}
    if count > 1 and not args.get("replace_all"):
        return {"ok": False, "error": "النص تكرر %d مرات — حدّد سياقًا أو replace_all" % count}
    data = data.replace(old, new) if args.get("replace_all") else data.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    return {"ok": True, "path": path, "replaced": count, "artifact": path,
            "note": "استبدل %d موضعً في %s" % (count, path)}

def glob(args):
    pattern = _bail(args, "pattern") or "**/*"
    base = config.safe_resolve(_bail(args, "dir") or ".")
    hits = []
    for root, dirs, files in os.walk(base):
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), base)
            if fnmatch.fnmatch(rel.replace("\\", "/"), pattern.replace("\\", "/")):
                hits.append(os.path.join(root, fn))
    hits.sort()
    return {"ok": True, "count": len(hits), "matches": hits[:200], "base": base,
            "truncated": len(hits) > 200}

def grep(args):
    pattern = _bail(args, "pattern")
    if not pattern:
        return {"ok": False, "error": "تحتاج regex في pattern"}
    base = config.safe_resolve(_bail(args, "path") or ".")
    include = _bail(args, "include") or "*"
    rx = re.compile(pattern)
    hits = []
    def walk(d):
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x not in {".git", "__pycache__", "node_modules", "jarvis_v2/evidence"}]
            for fn in files:
                if fnmatch.fnmatch(fn, include):
                    p = os.path.join(root, fn)
                    try:
                        if os.path.getsize(p) > config.MAX_FILE_BYTES:
                            continue
                        with open(p, "r", encoding="utf-8", errors="replace") as f:
                            for i, line in enumerate(f, 1):
                                if rx.search(line):
                                    hits.append({"file": os.path.relpath(p, config.BASE), "line": i,
                                                 "text": line.rstrip()[:200]})
                                    if len(hits) >= 200:
                                        break
                        if len(hits) >= 200:
                            break
                    except Exception:
                        continue
            if len(hits) >= 200:
                break
    if os.path.isfile(base):
        root, fn = os.path.split(base)
        for line_i, line in enumerate(open(base, "r", encoding="utf-8", errors="replace"), 1):
            if rx.search(line):
                hits.append({"file": os.path.relpath(base, config.BASE), "line": line_i, "text": line.rstrip()[:200]})
    else:
        walk(base)
    return {"ok": True, "count": len(hits), "matches": hits}