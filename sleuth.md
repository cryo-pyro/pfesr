got you, Pyromancer. here’s a single-file Python “sleuth” you can drop anywhere. it crawls a directory, **reads file contents** (full or capped), builds a **tree map**, emits a **concise summary**, and auto-generates **next-discussion prompts** based on what it finds.

### usage

```bash
python sleuth.py /path/to/dir               # quick scan (reads up to 1MB/file)
python sleuth.py . --full                   # read entire contents (slower)
python sleuth.py . --exclude ".git,node_modules,*.png,*.jpg"
python sleuth.py . --report report.md --json report.json
```

### sleuth.py

````python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sleuth: recursively map a directory, read files, summarize, and propose prompts.
Author: you
License: MIT
"""

import argparse, os, sys, re, json, hashlib, mimetypes
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

TEXT_EXT = {
    ".txt",".md",".markdown",".rst",".py",".js",".ts",".tsx",".jsx",".json",".yaml",".yml",
    ".toml",".ini",".cfg",".css",".scss",".sass",".html",".htm",".xml",".csv",".tsv",
    ".java",".go",".rs",".c",".h",".hpp",".cpp",".m",".mm",".swift",".kt",".rb",".php",
    ".sh",".bash",".zsh",".fish",".sql",".ipynb",".env",".dockerfile",".makefile",".mk",
}
BINARY_HINT = {".png",".jpg",".jpeg",".gif",".webp",".avif",".ico",".pdf",".zip",".gz",
               ".tar",".rar",".7z",".whl",".so",".dylib",".dll",".exe",".ttf",".otf",
               ".mp3",".wav",".flac",".mp4",".mov",".mkv",".heic",".bin"}

DEFAULT_EXCLUDES = {".git",".DS_Store","__pycache__",".pytest_cache",".venv","node_modules",
                    ".mypy_cache",".ruff_cache",".idea",".vscode","dist","build","target"}

LANG_BY_EXT = {
    ".py":"Python",".js":"JavaScript",".ts":"TypeScript",".tsx":"TypeScript/React",
    ".jsx":"JavaScript/React",".rb":"Ruby",".go":"Go",".rs":"Rust",".java":"Java",
    ".c":"C",".cpp":"C++",".h":"C/C++ header",".hpp":"C++ header",".kt":"Kotlin",
    ".swift":"Swift",".php":"PHP",".sh":"Shell",".bash":"Shell",".zsh":"Shell",
    ".sql":"SQL",".html":"HTML",".css":"CSS",".scss":"SCSS",".md":"Markdown",
    ".ipynb":"Jupyter Notebook"
}

def human(n: int) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024: return f"{n:.0f} {unit}"
        n/=1024
    return f"{n:.1f} PB"

def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in BINARY_HINT: return False
    if path.suffix.lower() in TEXT_EXT: return True
    mtype, _ = mimetypes.guess_type(str(path))
    return (mtype or "").startswith("text/") or path.suffix.lower() in {".json",".xml",".csv",".tsv",".ipynb"}

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]

def should_exclude(name: str, exclude_globs) -> bool:
    # match by exact folder/file name OR shell-style glob
    from fnmatch import fnmatch
    if name in DEFAULT_EXCLUDES: return True
    return any(fnmatch(name, pat) for pat in exclude_globs)

def read_file(path: Path, full: bool, cap: int) -> tuple[str,int,str]:
    try:
        if not is_probably_text(path):
            return ("", 0, "")
        data = b""
        if full:
            data = path.read_bytes()
        else:
            with path.open("rb") as f:
                data = f.read(cap+1)
                if len(data) > cap:
                    data = data[:cap]
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")
        return (text, len(data), sha256_bytes(data))
    except Exception as e:
        return (f"<<ERROR READING: {e}>>", 0, "")

def leaf_questions(findings) -> list[str]:
    q = []
    if findings["readmes"]:
        q.append("Should we treat the README(s) as the single source of truth and align code/docs to it?")
    if findings["envs"]["python"]:
        q.append("Pin Python deps (requirements.txt/poetry/pip-tools) and add a reproducible dev setup?")
    if findings["envs"]["node"]:
        q.append("Lock Node version and add scripts for build/test/lint in package.json?")
    if findings["has_tests"] and not findings["ci"]:
        q.append("Add CI (GitHub Actions) to run tests and linters on PRs?")
    if findings["largest"]:
        q.append("Refactor or split the largest files for readability/perf?")
    if findings["todos"]:
        q.append("Convert scattered TODO/FIXME comments into tracked issues or a TODO.md?")
    if findings["ipynb_count"]>0:
        q.append("Promote stable notebooks into modules with tests, keeping exploratory notebooks clean?")
    if findings["license_missing"]:
        q.append("Add a LICENSE to clarify reuse and obligations?")
    if findings["secrets"]:
        q.append("Move potential secrets to env/secret manager and add .gitignore rules?")
    if not q:
        q.append("What’s the primary deliverable here, and which directory is canonical for it?")
    return q

def main():
    ap = argparse.ArgumentParser(description="Sleuth directory: map, summarize, and propose prompts.")
    ap.add_argument("root", help="Directory to scan")
    ap.add_argument("--full", action="store_true", help="Read entire contents of each text-like file")
    ap.add_argument("--cap", type=int, default=1_000_000, help="Max bytes per file when not --full (default 1MB)")
    ap.add_argument("--exclude", type=str, default="", help="Comma-separated names/globs to exclude")
    ap.add_argument("--report", type=str, default="", help="Write markdown report to this path")
    ap.add_argument("--json", type=str, default="", help="Write machine-readable JSON summary to this path")
    ap.add_argument("--hash", action="store_true", help="Compute short sha256 of read content (text files)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        sys.exit(2)

    exclude_globs = [s.strip() for s in args.exclude.split(",") if s.strip()]
    total_files = 0
    total_bytes = 0
    ext_counts = Counter()
    lang_counts = Counter()
    largest = []  # list of (size, path)
    newest = []   # list of (mtime, path)
    file_items = []  # records for JSON
    todos = []
    secrets_hits = []
    has_tests = False
    ci = False
    readmes = []
    ipynb_count = 0
    envs = {"python": False, "node": False}
    license_missing = True

    # Build a textual tree map while scanning
    treelines = []
    root_prefix = str(root)
    now = datetime.now().isoformat(timespec="seconds")

    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded directories aggressively
        dirnames[:] = [d for d in dirnames if not should_exclude(d, exclude_globs)]
        rel_dir = Path(dirpath).relative_to(root)
        indent = "  " * (0 if rel_dir == Path(".") else len(rel_dir.parts))
        # Directory header
        treelines.append(f"{indent}{'/' if rel_dir == Path('.') else rel_dir.as_posix()+'/'}")

        # mark env and CI signals
        names = set(n.lower() for n in filenames)
        if "requirements.txt" in names or "pyproject.toml" in names or "poetry.lock" in names:
            envs["python"] = True
        if "package.json" in names or "pnpm-lock.yaml" in names or "yarn.lock" in names:
            envs["node"] = True
        if ".github" in (d.lower() for d in dirnames) or "azure-pipelines.yml" in names or "circleci" in (d.lower() for d in dirnames):
            ci = True

        for fn in sorted(filenames):
            if should_exclude(fn, exclude_globs): 
                continue
            p = Path(dirpath) / fn
            try:
                stat = p.stat()
            except Exception:
                continue

            fsize = stat.st_size
            total_files += 1
            total_bytes += fsize
            ext = p.suffix.lower()
            ext_counts[ext] += 1
            if ext in LANG_BY_EXT: lang_counts[LANG_BY_EXT[ext]] += 1
            if ext == ".ipynb": ipynb_count += 1
            if fn.lower() in {"readme.md","readme","readme.txt"}:
                readmes.append(str(p.relative_to(root)))
            if fn.lower().startswith("license"):
                license_missing = False

            largest.append((fsize, str(p.relative_to(root))))
            newest.append((stat.st_mtime, str(p.relative_to(root))))

            short_hash = ""
            text_preview = ""
            # read content (text-like only)
            text, read_bytes, digest = read_file(p, args.full, args.cap)
            if read_bytes > 0 and args.hash:
                short_hash = digest

            if text:
                # light heuristics
                if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", text, flags=re.I):
                    todos.append(str(p.relative_to(root)))
                if re.search(r"(?i)(api_key|secret|passwd|password|token)\s*[:=]\s*['\"][^'\"\\]{8,}", text):
                    secrets_hits.append(str(p.relative_to(root)))
                # try to pull a title from markdown/html
                title = None
                if ext in {".md",".markdown",".rst"}:
                    m = re.search(r"^#\s+(.+)$", text, flags=re.M)
                    if m: title = m.group(1).strip()
                elif ext in {".html",".htm"}:
                    m = re.search(r"<title>(.*?)</title>", text, flags=re.I|re.S)
                    if m: title = re.sub(r"\s+"," ", m.group(1)).strip()
                text_preview = (title or "").strip()

            treelines.append(f"{indent}  ├─ {fn} ({human(fsize)})" + (f"  [{short_hash}]" if short_hash else ""))

            file_items.append({
                "path": str(p.relative_to(root)),
                "size_bytes": fsize,
                "ext": ext or "<none>",
                "mtime": stat.st_mtime,
                "is_text": bool(text),
                "title_guess": text_preview,
                "sha256_16": short_hash,
            })

    largest.sort(reverse=True)        # by size
    newest.sort(reverse=True)         # by mtime
    largest_top = largest[:10]
    newest_top = newest[:10]

    findings = {
        "readmes": readmes,
        "envs": envs,
        "has_tests": any("/tests/" in f"/{p}/" or Path(p).name.lower().startswith("test_") for _, p in newest),
        "ci": ci,
        "largest": largest_top,
        "todos": todos,
        "ipynb_count": ipynb_count,
        "license_missing": license_missing,
        "secrets": secrets_hits,
    }

    prompts = leaf_questions(findings)

    # Build markdown report
    md = []
    md.append(f"# Sleuth Report\n\n**Root:** `{root}`  \n**When:** {now}\n")
    md.append("## Directory Map\n```\n" + "\n".join(treelines) + "\n```\n")
    md.append("## Summary\n")
    md.append(f"- **Total files:** {total_files}\n- **Total size:** {human(total_bytes)}\n")
    if readmes:
        md.append(f"- **READMEs:** {', '.join(readmes)}\n")
    if envs["python"] or envs["node"]:
        envbits = []
        if envs["python"]: envbits.append("Python")
        if envs["node"]: envbits.append("Node")
        md.append(f"- **Environments detected:** {', '.join(envbits)}\n")
    if ipynb_count:
        md.append(f"- **Notebooks:** {ipynb_count}\n")
    if findings["has_tests"]:
        md.append("- **Tests detected** ✅\n")
    if ci:
        md.append("- **CI detected** ✅\n")
    if license_missing:
        md.append("- **LICENSE missing** ⚠️\n")
    if secrets_hits:
        md.append(f"- **Potential secrets found in:** {len(secrets_hits)} files (review!)\n")

    # Top extensions / languages
    if ext_counts:
        top_ext = ", ".join(f"{k or '<none>'}×{v}" for k,v in ext_counts.most_common(8))
        md.append(f"\n**Top extensions:** {top_ext}\n")
    if lang_counts:
        top_lang = ", ".join(f"{k}×{v}" for k,v in lang_counts.most_common(8))
        md.append(f"\n**Languages:** {top_lang}\n")

    # Largest / Newest
    if largest_top:
        md.append("\n### Largest files\n")
        for sz, p in largest_top:
            md.append(f"- {p} — {human(sz)}")
    if newest_top:
        md.append("\n\n### Most recently modified\n")
        for mt, p in newest_top:
            ts = datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M:%S")
            md.append(f"- {p} — {ts}")

    # TODOs / Secrets (names only)
    if todos:
        md.append("\n\n### TODO/FIXME sightings\n")
        for p in sorted(set(todos))[:30]:
            md.append(f"- {p}")
        if len(set(todos))>30:
            md.append(f"- … and {len(set(todos))-30} more")

    if secrets_hits:
        md.append("\n\n### Potential secrets (pattern-based, manual verify!)\n")
        for p in sorted(set(secrets_hits))[:30]:
            md.append(f"- {p}")
        if len(set(secrets_hits))>30:
            md.append(f"- … and {len(set(secrets_hits))-30} more")

    # Prompts
    md.append("\n## Prompts for next discussion\n")
    for i, q in enumerate(prompts, 1):
        md.append(f"{i}. {q}")

    report_md = "\n".join(md)

    # JSON summary
    json_summary = {
        "root": str(root),
        "generated_at": now,
        "counts": {
            "files": total_files,
            "bytes": total_bytes,
            "by_extension": ext_counts,
            "by_language": lang_counts,
        },
        "largest_files": [{"path": p, "size_bytes": sz} for sz, p in largest_top],
        "newest_files": [{"path": p, "mtime": mt} for mt, p in newest_top],
        "readmes": readmes,
        "envs": envs,
        "has_tests": findings["has_tests"],
        "ci": ci,
        "ipynb_count": ipynb_count,
        "license_missing": license_missing,
        "potential_secrets": sorted(set(secrets_hits)),
        "todos_or_fixmes": sorted(set(todos)),
        "prompts": prompts,
        "files": file_items,
    }

    # Output
    print(report_md)
    if args.report:
        Path(args.report).write_text(report_md, encoding="utf-8")
    if args.json:
        # Convert Counters to plain dicts
        json_summary["counts"]["by_extension"] = dict(json_summary["counts"]["by_extension"])
        json_summary["counts"]["by_language"] = dict(json_summary["counts"]["by_language"])
        Path(args.json).write_text(json.dumps(json_summary, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
````

### notes

* “**speed of light??**” → default reads up to **1MB per file** for speed. Pass `--full` to truly read everything.
* pattern-based **secret** detection is conservative; still review hits.
* report renders to stdout and (optionally) `--report report.md`. a machine-readable `--json` is available for downstream tooling.

want a bash version too, or should we extend this to dump a clickable HTML tree?
