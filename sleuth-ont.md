Pyromancer, two quick fixes:

1. **Don’t `pip install` stdlib.** `argparse`, `pathlib`, `datetime`, `collections`, `os`, `re`, `json`, `math`, `mimetypes` are built-in. Remove those installs—`collections` fails because it’s part of Python itself, not a package.

2. Your error is my bug: I flipped the tuple from `most_common()`. It returns `(term, score)`, not `(score, term)`. Below is the **fixed full script** (also casts joins to str just in case).

---

### sleuth\_ontology.py (drop-in, corrected)

````python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sleuth Ontology: build a content summary + lightweight ontology (no external deps).
- Extracts Markdown/HTML titles & headings
- Extracts Python symbols (def/class) and JS/TS function-ish names
- Builds keyword sets (stopword-filtered) and co-occurrence graph
- Outputs ontology.md (with Mermaid mindmap) and ontology.json

Author: you
License: MIT
"""

import os, re, json, math, argparse, mimetypes
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

TEXT_EXT = {
    ".txt",".md",".markdown",".rst",".py",".js",".ts",".tsx",".jsx",".json",".yaml",".yml",
    ".toml",".ini",".cfg",".css",".scss",".sass",".html",".htm",".xml",".csv",".tsv",
}
BINARY_HINT = {".png",".jpg",".jpeg",".gif",".webp",".avif",".ico",".pdf",".zip",".gz",
               ".tar",".rar",".7z",".whl",".so",".dylib",".dll",".exe",".ttf",".otf",
               ".mp3",".wav",".flac",".mp4",".mov",".mkv",".heic",".bin"}

DEFAULT_EXCLUDES = {
    ".git",".DS_Store","__pycache__",".pytest_cache",".venv","node_modules",
    ".mypy_cache",".ruff_cache",".idea",".vscode","dist","build","target"
}

STOPWORDS = set("""
a about above after again against all am an and any are as at be because been before being
below between both but by could did do does doing down during each few for from further had has
have having he her here hers herself him himself his how i if in into is it its itself just
me more most my myself no nor not of off on once only or other our ours ourselves out over own
same she should so some such than that the their theirs them themselves then there these they this
those through to too under until up very was we were what when where which while who whom why will
with you your yours yourself yourselves
""".split())

def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in BINARY_HINT: return False
    if path.suffix.lower() in TEXT_EXT: return True
    mtype, _ = mimetypes.guess_type(str(path))
    return (mtype or "").startswith("text/") or path.suffix.lower() in {".json",".xml",".csv",".tsv"}

def tokenize(text: str):
    # simple tokens: letters/numbers + hyphen or apostrophe inside words
    for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-']{1,}\b", text):
        low = tok.lower()
        if low not in STOPWORDS and not low.isdigit() and len(low) > 2:
            yield low

def extract_md_headings(text: str):
    return [(len(m.group(1)), m.group(2).strip())
            for m in re.finditer(r"^(#{1,6})\s+(.+)$", text, flags=re.M)]

def extract_html_title(text: str):
    m = re.search(r"<title>(.*?)</title>", text, flags=re.I|re.S)
    return re.sub(r"\s+"," ", m.group(1)).strip() if m else None

def extract_python_symbols(text: str):
    syms = []
    for m in re.finditer(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text, flags=re.M):
        syms.append(("def", m.group(1)))
    for m in re.finditer(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]", text, flags=re.M):
        syms.append(("class", m.group(1)))
    return syms

def extract_js_symbols(text: str):
    syms = []
    for m in re.finditer(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        syms.append(("function", m.group(1)))
    for m in re.finditer(r"\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(", text):
        syms.append(("fn-var", m.group(1)))
    for m in re.finditer(r"\bexport\s+function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        syms.append(("export-fn", m.group(1)))
    return syms

def should_exclude(name: str, extra_excludes) -> bool:
    from fnmatch import fnmatch
    if name in DEFAULT_EXCLUDES: return True
    return any(fnmatch(name, pat) for pat in extra_excludes)

def read_text_file(path: Path, cap: int) -> str:
    try:
        data = path.read_bytes()
        if cap and len(data) > cap:
            data = data[:cap]
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("latin-1", errors="replace")
    except Exception as e:
        return f"<<ERROR READING: {e}>>"

def build_cooccurrence(top_terms_per_file, window_pairs=250):
    co = Counter()
    for terms in top_terms_per_file.values():
        terms = terms[:50]
        pairs = 0
        for i in range(len(terms)):
            for j in range(i+1, len(terms)):
                a, b = sorted((terms[i], terms[j]))
                co[(a, b)] += 1
                pairs += 1
                if pairs >= window_pairs:
                    break
            if pairs >= window_pairs:
                break
    return co

def main():
    ap = argparse.ArgumentParser(description="Generate ontology (summary + concept map) for a directory.")
    ap.add_argument("root", help="Directory to scan")
    ap.add_argument("--cap", type=int, default=1_000_000, help="Max bytes per file to read (default 1MB)")
    ap.add_argument("--exclude", type=str, default="", help="Comma-separated names/globs to exclude")
    ap.add_argument("--out-md", type=str, default="ontology.md", help="Output Markdown file")
    ap.add_argument("--out-json", type=str, default="ontology.json", help="Output JSON file")
    ap.add_argument("--topn", type=int, default=12, help="Top keywords per file")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"error: {root} is not a directory", flush=True)
        return 2

    exclude_globs = [s.strip() for s in args.exclude.split(",") if s.strip()]

    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_exclude(d, exclude_globs)]
        for fn in filenames:
            if should_exclude(fn, exclude_globs): 
                continue
            p = Path(dirpath) / fn
            if is_probably_text(p):
                files.append(p)

    per_file = {}
    df_counter = Counter()
    for p in files:
        text = read_text_file(p, args.cap)
        ext = p.suffix.lower()
        tokens = list(tokenize(text))
        tf = Counter(tokens)

        title = None
        headings = []
        symbols = []

        if ext in {".md",".markdown",".rst"}:
            hs = extract_md_headings(text)
            headings = [("#"*lvl + " " + h) for (lvl, h) in hs]
            for lvl, h in hs:
                if lvl == 1:
                    title = h
                    break
        elif ext in {".html",".htm"}:
            t = extract_html_title(text)
            if t: title = t

        if ext == ".py":
            symbols = [f"{k}: {v}" for (k, v) in extract_python_symbols(text)]
        elif ext in {".js",".jsx",".ts",".tsx"}:
            symbols = [f"{k}: {v}" for (k, v) in extract_js_symbols(text)]

        per_file[str(p.relative_to(root))] = {
            "ext": ext or "<none>",
            "title": title,
            "headings": headings[:30],
            "symbols": symbols[:40],
            "tf": dict(tf),
        }
        for term in set(tf.keys()):
            df_counter[term] += 1

    N = max(1, len(per_file))
    top_terms_per_file = {}
    global_score = Counter()
    for path, info in per_file.items():
        tf = info["tf"]
        scored = []
        for term, freq in tf.items():
            df = df_counter[term]
            idf = math.log((N + 1) / (df + 1)) + 1.0
            score = (1 + math.log(freq)) * idf
            scored.append((score, term))
            global_score[term] += score
        scored.sort(reverse=True)
        top_terms_per_file[path] = [t for _, t in scored[:args.topn]]
        info["top_terms"] = top_terms_per_file[path]
        if len(info["tf"]) > 0:
            info["tf"] = dict((t, tf[t]) for _, t in sorted(((v,k) for k,v in tf.items()), reverse=True)[:100])

    # ✅ FIX: correct order from most_common() — returns (term, score)
    global_topics = [term for term, _ in global_score.most_common(30)]

    co = build_cooccurrence(top_terms_per_file)
    top_edges = [(a,b,c) for ((a,b),c) in sorted(co.items(), key=lambda x: x[1], reverse=True)[:40]]

    hierarchy = defaultdict(list)
    for path in per_file.keys():
        parts = Path(path).parts
        if len(parts) > 1:
            hierarchy[parts[0]].append(path)
        else:
            hierarchy["_root"].append(path)

    now = datetime.now().isoformat(timespec="seconds")

    md = []
    md.append(f"# Ontology & Content Summary\n\n**Root:** `{root}`  \n**When:** {now}\n")
    md.append("## Global Topics (top terms)\n")
    md.append(", ".join(str(t) for t in global_topics) + "\n")  # cast to str defensively

    md.append("\n## Concept Map (Mermaid mindmap)\n")
    md.append("```mermaid\nmindmap\n  root((Project))\n")
    for t in global_topics[:12]:
        md.append(f"    {t}\n")
    for a, b, w in top_edges[:20]:
        md.append(f"    {a}:::edge\n      {b}({b})\n")
    md.append("```\n")

    md.append("## Structure Hints\n")
    for top, paths in sorted(hierarchy.items()):
        md.append(f"### {top}\n")
        for p in sorted(paths)[:8]:
            info = per_file[p]
            title = f" — {info['title']}" if info.get("title") else ""
            tops = ", ".join(info.get("top_terms", [])[:6])
            md.append(f"- `{p}`{title} — _{tops}_")
        if len(paths) > 8:
            md.append(f"- … and {len(paths)-8} more")

    md.append("\n## File Summaries (headings & symbols)\n")
    for p in sorted(per_file.keys()):
        info = per_file[p]
        md.append(f"### `{p}`")
        if info.get("title"):
            md.append(f"- **Title:** {info['title']}")
        if info.get("headings"):
            md.append(f"- **Headings:**")
            for h in info["headings"][:10]:
                md.append(f"  - {h}")
        if info.get("symbols"):
            md.append(f"- **Symbols:**")
            for s in info["symbols"][:12]:
                md.append(f"  - {s}")
        if info.get("top_terms"):
            md.append(f"- **Top terms:** {', '.join(info['top_terms'])}")
        md.append("")

    md.append("\n## Prompts for next discussion\n")
    md.extend([
        "1. Do these global topics match the project’s intended ontology? What’s missing or over-weighted?",
        "2. Which folder should be considered canonical for definitions (glossary/spec)?",
        "3. Should we promote certain headings into a formal taxonomy (e.g., Entities → Attributes → Relations)?",
        "4. Which symbols (functions/classes) should be public API vs. internal?",
        "5. Any terms here that should be merged/aliased (e.g., synonyms) or banned?",
    ])

    md_text = "\n".join(md)

    out = {
        "root": str(root),
        "generated_at": now,
        "global_topics": global_topics,
        "cooccurrence_edges": [{"a": a, "b": b, "weight": w} for a,b,w in top_edges],
        "files": per_file,
        "hierarchy": {k: v for k, v in hierarchy.items()},
    }

    Path(args.out_md).write_text(md_text, encoding="utf-8")
    Path(args.out_json).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {args.out_md} and {args.out_json}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
````

---

### Run it (no extra installs)

```bash
# activate your venv (already done)
python sleuth_ontology.py . \
  --exclude ".git,node_modules,*.jpg,*.png,*.pdf" \
  --out-md ontology.md \
  --out-json ontology.json
```

Want me to **merge ontology mode into `sleuth.py`** (e.g., `--ontology ontology.md` to produce both reports in one go)?


