"""
Refresh the profile README from two sources:
  1. Your latest public repositories (GitHub REST API, no token needed for public data)
  2. The newest headings in LEARNING_LOG.md

Only text between the marker comments is replaced, so the rest of the README is never touched.
Standard library only — nothing to install.
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
LOG = ROOT / "LEARNING_LOG.md"

USERNAME = os.environ.get("GITHUB_USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER")
TOKEN = os.environ.get("GITHUB_TOKEN")  # optional, raises the API rate limit
MAX_REPOS = 5
MAX_LOG_ENTRIES = 5

LOG_HEADING = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s+[—-]\s+(.+?)\s*$")


def fetch_repos(username: str) -> list[dict]:
    url = f"https://api.github.com/users/{username}/repos?sort=created&direction=desc&per_page=30"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        repos = json.load(resp)
    # Skip forks and the profile repo itself
    return [r for r in repos if not r["fork"] and r["name"].lower() != username.lower()][:MAX_REPOS]


def render_repos(repos: list[dict]) -> str:
    if not repos:
        return "_No public projects yet — first one coming soon._"
    lines = []
    for r in repos:
        desc = (r.get("description") or "No description yet").strip()
        lang = f" · `{r['language']}`" if r.get("language") else ""
        lines.append(f"- [{r['name']}]({r['html_url']}) — {desc}{lang}")
    return "\n".join(lines)


def read_log_entries(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = LOG_HEADING.match(line)
        if m:
            entries.append((m.group(1), m.group(2)))
    entries.sort(key=lambda e: e[0], reverse=True)
    return entries[:MAX_LOG_ENTRIES]


def render_log(entries: list[tuple[str, str]]) -> str:
    if not entries:
        return "_No entries yet._"
    lines = [f"- **{date}** — {title}" for date, title in entries]
    lines.append("\n[Full log →](LEARNING_LOG.md)")
    return "\n".join(lines)


def replace_block(text: str, tag: str, body: str) -> str:
    pattern = re.compile(rf"(<!-- {tag}:START -->)(.*?)(<!-- {tag}:END -->)", re.DOTALL)
    if not pattern.search(text):
        print(f"warning: markers for {tag} not found in README", file=sys.stderr)
        return text
    return pattern.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def main() -> int:
    if not USERNAME:
        print("Set GITHUB_USERNAME (GitHub Actions sets GITHUB_REPOSITORY_OWNER automatically).", file=sys.stderr)
        return 1

    original = README.read_text(encoding="utf-8")
    updated = original

    try:
        updated = replace_block(updated, "REPOS", render_repos(fetch_repos(USERNAME)))
    except Exception as exc:  # network/API issues should not wipe the README
        print(f"warning: could not fetch repos ({exc}); leaving that section unchanged", file=sys.stderr)

    updated = replace_block(updated, "LOG", render_log(read_log_entries(LOG)))

    if updated != original:
        README.write_text(updated, encoding="utf-8")
        print("README updated.")
    else:
        print("README already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
