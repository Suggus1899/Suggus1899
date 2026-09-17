import html
import json
import math
import os
import urllib.request
import urllib.parse
from collections import Counter
from pathlib import Path


API = "https://api.github.com/graphql"
USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "Suggus1899")
TOKEN = os.environ["GITHUB_TOKEN"]


def graphql(query, variables):
    request = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-telemetry",
        },
    )
    with urllib.request.urlopen(request) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


def rest(path, params):
    url = f"https://api.github.com{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "profile-telemetry",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


profile = graphql(
    """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false) {
          nodes { stargazerCount primaryLanguage { name } }
          pageInfo { hasNextPage }
          totalCount
        }
        repositoriesContributedTo(
          first: 1,
          includeUserRepositories: true,
          privacy: PUBLIC,
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
        ) { totalCount }
        contributionsCollection { contributionYears }
      }
    }
    """,
    {"login": USERNAME},
)["user"]

commits = 0
for year in profile["contributionsCollection"]["contributionYears"]:
    contribution = graphql(
        """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              commitContributionsByRepository(maxRepositories: 100) {
                repository { nameWithOwner }
                contributions { totalCount }
              }
            }
          }
        }
        """,
        {
            "login": USERNAME,
            "from": f"{year}-01-01T00:00:00Z",
            "to": f"{year}-12-31T23:59:59Z",
        },
    )
    repository_contributions = contribution["user"]["contributionsCollection"]["commitContributionsByRepository"]
    commits += sum(
        item["contributions"]["totalCount"]
        for item in repository_contributions
        if item["repository"]["nameWithOwner"].lower() != f"{USERNAME}/{USERNAME}".lower()
    )

repos = profile["repositories"]["nodes"]
if profile["repositories"]["pageInfo"]["hasNextPage"]:
    raise RuntimeError("More than 100 public repositories: pagination is required before publishing telemetry")
public_prs = rest("/search/issues", {"q": f"author:{USERNAME} type:pr is:public", "per_page": 1})["total_count"]
public_issues = rest("/search/issues", {"q": f"author:{USERNAME} type:issue is:public", "per_page": 1})["total_count"]
stats = [
    ("STARS RECEIVED", sum(repo["stargazerCount"] for repo in repos)),
    ("GITHUB COMMITS", commits),
    ("PUBLIC PRs", public_prs),
    ("PUBLIC ISSUES", public_issues),
    ("REPOS CONTRIBUTED", profile["repositoriesContributedTo"]["totalCount"]),
]
language_counts = Counter(
    repo["primaryLanguage"]["name"] if repo["primaryLanguage"] else "No language"
    for repo in repos
)
top_languages = language_counts.most_common(4)
other_count = sum(language_counts.values()) - sum(count for _, count in top_languages)
languages = top_languages + ([('Other / none', other_count)] if other_count else [])
assert sum(count for _, count in languages) == len(repos)

colors = ["#f89820", "#5382a1", "#c4a484", "#7cb342", "#8d6e63"]
circumference = 2 * math.pi * 54
total = sum(count for _, count in languages) or 1
offset = 0.0
arcs = []
legend = []
for index, ((language, count), color) in enumerate(zip(languages, colors)):
    length = circumference * count / total
    arcs.append(
        f'<circle class="arc" style="--i:{index};--delay:{index * 0.12:.2f}s" cx="694" cy="143" r="54" '
        f'fill="none" stroke="{color}" stroke-width="25" '
        f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" '
        f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 694 143)"/>'
    )
    y = 85 + index * 27
    legend.append(
        f'<g class="legend" style="--i:{index}">'
        f'<rect x="492" y="{y - 12}" width="14" height="14" rx="2" fill="{color}"/>'
        f'<text x="517" y="{y}" class="label">{html.escape(language)}</text>'
        f'<text x="620" y="{y}" class="value small">{count}</text>'
        '</g>'
    )
    offset += length

stat_rows = []
for index, (label, value) in enumerate(stats):
    y = 83 + index * 29
    stat_rows.append(
        f'<g class="row" style="--i:{index}">'
        f'<text x="56" y="{y}" class="label">{label}</text>'
        f'<text x="310" y="{y}" class="value">{value}</text>'
        '</g>'
    )

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="260" viewBox="0 0 900 260" role="img" aria-labelledby="title desc">
  <title id="title">Live GitHub telemetry for {html.escape(USERNAME)}</title>
  <desc id="desc">Public GitHub totals and repository languages, refreshed automatically.</desc>
  <defs>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <style>
      text {{ font-family: 'Courier New', Consolas, monospace; }}
      .panel {{ fill:#17120f; stroke:#6f4e37; stroke-width:1; }}
      .heading {{ fill:#f89820; font-size:23px; font-weight:700; }}
      .label {{ fill:#f3e5c8; font-size:14px; }}
      .value {{ fill:#7cb342; font-size:15px; font-weight:700; text-anchor:end; }}
      .small {{ fill:#f3e5c8; font-size:13px; }}
      .row {{ opacity:0; animation:enter .5s cubic-bezier(.22,.8,.3,1) forwards; animation-delay:calc(var(--i) * .11s); }}
      .legend {{ opacity:0; animation:legendIn .45s ease-out forwards; animation-delay:calc(.2s + var(--i) * .1s); }}
      .arc {{ animation:arcIn .9s cubic-bezier(.22,.8,.3,1) both,arcGlow 4s ease-in-out infinite; animation-delay:var(--delay),calc(1s + var(--i) * -.4s); }}
      .sweep {{ transform-origin:694px 143px; animation:spin 7s linear infinite; }}
      .count {{ transform-box:fill-box; transform-origin:center; animation:countIn .7s .55s cubic-bezier(.2,.9,.3,1.25) both; }}
      .online {{ transform-box:fill-box; transform-origin:center; animation:blink 1.4s ease-in-out infinite; }}
      .scan {{ animation:scan 4.8s linear infinite; }}
      @keyframes enter {{ from {{ opacity:0; transform:translateX(-12px); }} to {{ opacity:1; transform:none; }} }}
      @keyframes legendIn {{ from {{ opacity:0; transform:translateY(7px); }} to {{ opacity:1; transform:none; }} }}
      @keyframes arcIn {{ from {{ opacity:0; stroke-dasharray:0 {circumference:.2f}; }} }}
      @keyframes arcGlow {{ 50% {{ opacity:.7; filter:url(#glow); }} }}
      @keyframes countIn {{ from {{ opacity:0; transform:scale(.55); }} to {{ opacity:1; transform:scale(1); }} }}
      @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
      @keyframes scan {{ from {{ transform:translateY(-18px); }} to {{ transform:translateY(276px); }} }}
      @keyframes blink {{ 50% {{ opacity:.32; transform:scale(.72); }} }}
      @media (prefers-reduced-motion:reduce) {{ .row,.legend,.arc,.sweep,.count,.online,.scan {{ animation:none; opacity:1; transform:none; }} }}
    </style>
  </defs>
  <rect width="900" height="260" rx="12" fill="#0b0908"/>
  <rect class="panel" x="12" y="12" width="414" height="236" rx="9"/>
  <rect class="panel" x="438" y="12" width="450" height="236" rx="9"/>
  <text x="36" y="52" class="heading">JVM:// LIVE STATS</text>
  <circle class="online" cx="393" cy="43" r="5" fill="#7cb342" filter="url(#glow)"/>
  {''.join(stat_rows)}
  <text x="468" y="52" class="heading">LANGUAGES:// REPOS</text>
  {''.join(legend)}
  <circle cx="694" cy="143" r="54" fill="none" stroke="#3e2723" stroke-width="25"/>
  {''.join(arcs)}
  <circle class="sweep" cx="694" cy="143" r="72" fill="none" stroke="#f89820" stroke-width="2" stroke-linecap="round" stroke-dasharray="4 22" opacity=".5"/>
  <circle cx="694" cy="143" r="35" fill="#17120f"/>
  <g class="count"><text x="694" y="139" text-anchor="middle" class="value" style="font-size:20px">{profile["repositories"]["totalCount"]}</text>
  <text x="694" y="157" text-anchor="middle" class="label" style="font-size:9px">OWN PUBLIC</text></g>
  <text x="854" y="229" text-anchor="end" class="label" style="font-size:10px;opacity:.65">HOURLY // GITHUB API</text>
  <rect class="scan" x="12" y="-18" width="876" height="18" fill="#f89820" opacity=".025"/>
</svg>'''

output = Path(__file__).resolve().parents[1] / "assets" / "github-telemetry.svg"
output.write_text(svg, encoding="utf-8")
