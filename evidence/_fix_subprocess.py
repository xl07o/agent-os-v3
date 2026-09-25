#!/usr/bin/env python3
"""Fix subprocess text=True calls missing encoding on Windows (cp1252 crash).
Insert  encoding="utf-8"  (and errors="replace" when absent) after the text=true keyword.
"""
import ast, os, sys

ROOT = os.getcwd()


def find_sites():
    sites = set()
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "data", "evidence",
                                                "output", "projects", "logs", "node_modules")]
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(root, f)
            try:
                tree = ast.parse(open(p, encoding="utf-8").read())
            except Exception:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = None
                if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "subprocess":
                    name = fn.attr
                if name not in ("run", "check_output", "call", "Popen"):
                    continue
                has_text = any(k.arg in ("text", "universal_newlines") for k in node.keywords)
                has_enc = any(k.arg == "encoding" for k in node.keywords)
                if not has_text or has_enc:
                    continue
                text_kw = next(k for k in node.keywords if k.arg in ("text", "universal_newlines"))
                has_err = any(k.arg == "errors" for k in node.keywords)
                sites.add((p, text_kw.lineno, text_kw.end_lineno, has_err))
    return sites


def patch_line(line, has_err):
    # find text=True / text = True token on the line
    kw = "text=True"
    alt = "text = True"
    pos = line.find(kw)
    if pos == -1:
        pos = line.find(alt)
        if pos == -1:
            return None
        end = pos + len(alt)
    else:
        end = pos + len(kw)
    extra = "encoding=\"utf-8\"" if has_err else "encoding=\"utf-8\", errors=\"replace\""
    return line[:end] + ", " + extra + line[end:]


def main():
    sites = sorted(find_sites())
    if not sites:
        print("No sites found.")
        return 1
    changed = 0
    for p, lno, e_lno, has_err in sites:
        lines = open(p, encoding="utf-8").read().splitlines(keepends=True)
        for i in range(lno - 1, e_lno):
            new = patch_line(lines[i], has_err)
            if new is not None:
                lines[i] = new
                break
        open(p, "w", encoding="utf-8").write("".join(lines))
        changed += 1
        print(f"PATCHED {p}:{lno} (errors already present={has_err})")
    print(f"\n{changed} sites patched")
    return 0


if __name__ == "__main__":
    sys.exit(main())