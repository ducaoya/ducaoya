#!/usr/bin/env python3
"""Generate self-hosted GitHub stats cards (stats.svg, top-langs.svg).

Reads data from the GitHub REST API and writes plain SVG files, so the profile
README never depends on a third-party card service that can rate-limit or die.

Usage: GITHUB_TOKEN=xxx python3 scripts/gen_stats.py [output_dir]
"""

import json
import os
import sys
import urllib.request

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
USER = os.environ.get("GH_USER") or "ducaoya"

BG = "#0D1117"
TITLE = "#38BDF8"
LABEL = "#8b949e"
TEXT = "#c9d1d9"
ACCENT = "#8B5CF6"
BAR_COLORS = ["#38BDF8", "#8B5CF6", "#6366F1", "#0EA5E9", "#A78BFA", "#22D3EE"]


def api(path):
    req = urllib.request.Request(API + path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "ducaoya-profile-stats")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fmt(n):
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def collect():
    user = api(f"/users/{USER}")
    repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
    repos = [r for r in repos if not r.get("fork")]

    stars = sum(r.get("stargazers_count", 0) for r in repos)
    forks = sum(r.get("forks_count", 0) for r in repos)

    # Language bytes: only the most recently pushed repos, to keep request count low.
    recent = sorted(repos, key=lambda r: r.get("pushed_at") or "", reverse=True)[:25]
    lang_bytes = {}
    for repo in recent:
        try:
            data = api(f"/repos/{USER}/{repo['name']}/languages")
        except Exception as exc:  # noqa: BLE001 - one repo must not kill the run
            print(f"warn: languages {repo['name']}: {exc}", file=sys.stderr)
            continue
        for name, size in data.items():
            lang_bytes[name] = lang_bytes.get(name, 0) + size

    return {
        "stars": stars,
        "forks": forks,
        "repos": user.get("public_repos", len(repos)),
        "followers": user.get("followers", 0),
        "following": user.get("following", 0),
        "langs": sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True),
    }


def stats_svg(data):
    rows = [
        ("Total Stars", fmt(data["stars"]), 0, 0),
        ("Public Repos", fmt(data["repos"]), 1, 0),
        ("Followers", fmt(data["followers"]), 0, 1),
        ("Total Forks", fmt(data["forks"]), 1, 1),
        ("Following", fmt(data["following"]), 0, 2),
        ("Top Language", data["langs"][0][0] if data["langs"] else "-", 1, 2),
    ]
    parts = []
    for label, value, col, row in rows:
        x = 28 + col * 226
        y = 74 + row * 32
        parts.append(
            f'<circle cx="{x + 4}" cy="{y - 4}" r="4" fill="{ACCENT}" opacity="0.85"/>'
            f'<text x="{x + 16}" y="{y}" font-size="13" fill="{LABEL}">{esc(label)}</text>'
            f'<text x="{x + 186}" y="{y}" font-size="14" font-weight="700" '
            f'fill="{TEXT}" text-anchor="end">{esc(value)}</text>'
        )
    return svg(480, 175, f"{USER}'s GitHub Stats", parts)


def langs_svg(data):
    total = sum(b for _, b in data["langs"]) or 1
    top = data["langs"][:6]
    parts = []
    for i, (name, size) in enumerate(top):
        pct = size / total * 100
        y = 70 + i * 18
        width = max(2.0, 150 * pct / 100)
        color = BAR_COLORS[i % len(BAR_COLORS)]
        parts.append(
            f'<text x="28" y="{y}" font-size="12" fill="{TEXT}">{esc(name)}</text>'
            f'<rect x="130" y="{y - 9}" width="150" height="8" rx="4" fill="#21262d"/>'
            f'<rect x="130" y="{y - 9}" width="{width:.1f}" height="8" rx="4" fill="{color}"/>'
            f'<text x="290" y="{y}" font-size="12" fill="{LABEL}">{pct:.1f}%</text>'
        )
    return svg(480, 175, "Most Used Languages", parts)


def svg(width, height, title, parts):
    body = "\n  ".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">\n'
        f'  <rect width="{width}" height="{height}" rx="8" fill="{BG}"/>\n'
        f'  <g font-family="Segoe UI,Helvetica,Arial,sans-serif">\n'
        f'  <text x="28" y="34" font-size="16" font-weight="600" fill="{TITLE}">{esc(title)}</text>\n'
        f"  {body}\n"
        f"  </g>\n"
        f"</svg>\n"
    )


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "dist"
    os.makedirs(out, exist_ok=True)
    data = collect()
    with open(os.path.join(out, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(stats_svg(data))
    with open(os.path.join(out, "top-langs.svg"), "w", encoding="utf-8") as f:
        f.write(langs_svg(data))
    print(f"wrote {out}/stats.svg and {out}/top-langs.svg")


if __name__ == "__main__":
    main()
