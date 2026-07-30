#!/usr/bin/env python3
"""
Merge projects.json (hand-curated) with live GitHub data into merged.json.

You control: name, repo, logo, description, tags and the order of the array.
Fetched:     stars, language byte split (for the donut) and pushed_at.

A repo that fails to fetch still renders -- it just falls back to the config.
Run inside the Action so GITHUB_TOKEN is present; without one you get the
unauthenticated rate limit, which is enough for a handful of repos.
"""
import json
import os
import sys
import urllib.request

TOKEN = os.environ.get("GITHUB_TOKEN", "")


def gh(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "projects-panel"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def main():
    with open("projects.json", encoding="utf-8") as f:
        projects = json.load(f)

    for p in projects:
        repo = (p.get("repo", "").strip()
                .replace("https://github.com/", "").replace("http://github.com/", "")
                .rstrip("/"))
        p["repo"] = repo
        try:
            info = gh(f"https://api.github.com/repos/{repo}")
            p["stars"] = info.get("stargazers_count", 0)
            p["pushed_at"] = info.get("pushed_at")
            if not p.get("description"):
                p["description"] = info.get("description") or ""
            p["languages"] = gh(f"https://api.github.com/repos/{repo}/languages")
        except Exception as exc:
            print(f"warn: could not fetch {repo}: {exc}", file=sys.stderr)
            p.setdefault("stars", 0)
            p.setdefault("languages", {})
            p.setdefault("pushed_at", None)

    with open("merged.json", "w", encoding="utf-8") as f:
        json.dump(projects, f)
    print(f"merged {len(projects)} projects")


if __name__ == "__main__":
    main()
