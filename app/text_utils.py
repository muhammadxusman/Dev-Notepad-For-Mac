from __future__ import annotations

import json
import re


def format_json(text: str) -> str:
    return json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n"


def minify_json(text: str) -> str:
    return json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)


def trim_trailing_spaces(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines())


def sort_lines(text: str) -> str:
    return "\n".join(sorted(text.splitlines()))


def dedupe_lines(text: str) -> str:
    seen: set[str] = set()
    result: list[str] = []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            result.append(line)
    return "\n".join(result)


def tabs_to_spaces(text: str, width: int = 4) -> str:
    return text.replace("\t", " " * width)


def spaces_to_tabs(text: str, width: int = 4) -> str:
    return re.sub(rf" {{{width}}}", "\t", text)


def detect_language(text: str, title: str = "") -> str:
    lowered = title.lower()
    suffix_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".json": "JSON",
        ".html": "HTML",
        ".css": "CSS",
        ".sh": "Bash",
        ".sql": "SQL",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".md": "Markdown",
    }
    for suffix, language in suffix_map.items():
        if lowered.endswith(suffix):
            return language
    stripped = text.strip()
    if not stripped:
        return "Plain Text"
    if stripped.startswith(("{", "[")):
        try:
            json.loads(stripped)
            return "JSON"
        except json.JSONDecodeError:
            pass
    if stripped.startswith(("<!doctype", "<html", "<div", "<section")):
        return "HTML"
    if re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN)\b", stripped, re.I):
        return "SQL"
    if stripped.startswith(("#!/bin/bash", "#!/usr/bin/env bash")) or re.search(r"\b(echo|curl|grep|awk)\b", stripped):
        return "Bash"
    if re.search(r"\b(def|class|import|from)\b", stripped) and ":" in stripped:
        return "Python"
    if re.search(r"\b(function|const|let|=>|console\.log)\b", stripped):
        return "JavaScript"
    return "Plain Text"


TEMPLATES = {
    "Python Script Starter": """#!/usr/bin/env python3

def main() -> None:
    pass


if __name__ == "__main__":
    main()
""",
    "JSON Object": """{
  "name": "",
  "value": ""
}
""",
    "SQL Query": """SELECT *
FROM table_name
WHERE condition = true
ORDER BY created_at DESC
LIMIT 100;
""",
    "Bash Command Block": """#!/usr/bin/env bash
set -euo pipefail

""",
    "API Request": """POST /api/resource HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>

{
  "key": "value"
}
""",
    "Markdown Checklist": """## Checklist

- [ ] 
- [ ] 
- [ ] 
""",
    ".env Sample": """APP_ENV=local
API_URL=http://localhost:8000
TOKEN=
""",
}
