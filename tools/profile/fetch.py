"""Collect profile telemetry from GitHub, Docker Hub and GHCR into data/profile.json."""

import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
UA = "james-d-elliott-profile-generator"


def token():
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        sys.exit("no GITHUB_TOKEN/GH_TOKEN set and `gh auth token` unavailable")


TOKEN = None


def http(url, accept="application/vnd.github+json", body=None, auth=True):
    headers = {"User-Agent": UA, "Accept": accept}
    if auth:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()


def rest(path, accept="application/vnd.github+json"):
    return json.loads(http(API + path, accept))


def gql(query):
    res = json.loads(http(API + "/graphql", body={"query": query}))
    if res.get("errors"):
        raise RuntimeError(res["errors"])
    return res["data"]


def user_stats(login):
    d = gql(f"""{{user(login:"{login}"){{
      createdAt followers{{totalCount}}
      pullRequests{{totalCount}} merged:pullRequests(states:MERGED){{totalCount}}
      issues{{totalCount}} issueComments{{totalCount}}
      repositoryDiscussions{{totalCount}} repositoryDiscussionComments{{totalCount}}
      contributionsCollection{{
        contributionYears
        totalCommitContributions totalIssueContributions totalPullRequestContributions
        totalPullRequestReviewContributions restrictedContributionsCount
        contributionCalendar{{totalContributions weeks{{contributionDays{{date contributionCount}}}}}}
      }}
    }}}}""")["user"]
    cc = d.pop("contributionsCollection")
    cal = cc.pop("contributionCalendar")
    years = {}
    for y in cc.pop("contributionYears"):
        c = gql(f"""{{user(login:"{login}"){{contributionsCollection(from:"{y}-01-01T00:00:00Z",to:"{y}-12-31T23:59:59Z"){{
          totalCommitContributions totalIssueContributions totalPullRequestContributions
          totalPullRequestReviewContributions restrictedContributionsCount
          contributionCalendar{{totalContributions}}}}}}}}""")["user"]["contributionsCollection"]
        c["total"] = c.pop("contributionCalendar")["totalContributions"]
        years[str(y)] = c
    days = [[day["date"], day["contributionCount"]] for w in cal["weeks"] for day in w["contributionDays"]]
    return {
        "created_at": d["createdAt"],
        "followers": d["followers"]["totalCount"],
        "pull_requests": d["pullRequests"]["totalCount"],
        "merged": d["merged"]["totalCount"],
        "issues": d["issues"]["totalCount"],
        "issue_comments": d["issueComments"]["totalCount"],
        "discussions": d["repositoryDiscussions"]["totalCount"],
        "discussion_comments": d["repositoryDiscussionComments"]["totalCount"],
        "last12": cc,
        "calendar": days,
        "years": years,
    }


def stargazer_page(repo, page):
    return rest(f"/repos/{repo}/stargazers?per_page=100&page={page}", "application/vnd.github.star+json")


def star_history(repo, stars, samples=40):
    """Return [[star_number, starred_at], ...]. Small repos: every star. Large repos: sampled pages."""
    pages = min(400, max(1, math.ceil(stars / 100)))  # the API refuses pages past 400 (40k stars)
    if stars <= 3000:
        out = []
        for p in range(1, pages + 1):
            for i, s in enumerate(stargazer_page(repo, p)):
                out.append([(p - 1) * 100 + i + 1, s["starred_at"]])
        return out
    step = max(1, pages // samples)
    wanted = sorted(set(list(range(1, pages + 1, step)) + [pages]))
    out = []
    for p in wanted:
        page = stargazer_page(repo, p)
        if page:
            out.append([(p - 1) * 100 + 1, page[0]["starred_at"]])
            if p == pages:
                out.append([(p - 1) * 100 + len(page), page[-1]["starred_at"]])
    return out


def docker_pulls(name):
    return json.loads(http(f"https://hub.docker.com/v2/repositories/{name}/", "application/json", auth=False))["pull_count"]


def ghcr_downloads(url):
    html = http(url, "text/html", auth=False)
    m = re.search(r'Total downloads</span>\s*<h3 title="(\d+)"', html)
    if not m:
        raise RuntimeError("could not find GHCR total downloads on package page")
    return int(m.group(1))


def release_downloads(repo):
    total, page = 0, 1
    while True:
        rels = rest(f"/repos/{repo}/releases?per_page=100&page={page}")
        total += sum(a["download_count"] for r in rels for a in r["assets"])
        if len(rels) < 100:
            return total
        page += 1


def dependents(repo):
    """GitHub's dependency graph "Used by" counts (repositories and packages that depend on the repo)."""
    html = http(f"https://github.com/{repo}/network/dependents", "text/html", auth=False)
    flat = re.sub(r"\s+", " ", html)
    out = {}
    for kind in ("Repositories", "Packages"):
        m = re.search(r"([\d,]+) " + kind + r" </a>", flat)
        out[kind.lower()] = int(m.group(1).replace(",", "")) if m else 0
    return out


def commit_date(repo, sha):
    return rest(f"/repos/{repo}/commits/{sha}")["commit"]["committer"]["date"]


def releases(repo, n=3):
    """Latest releases, falling back to tags for repos that only tag."""
    rels = [r for r in rest(f"/repos/{repo}/releases?per_page={n}") if not r["draft"]]
    if rels:
        return [{"repo": repo, "tag": r["tag_name"], "date": r["published_at"], "url": r["html_url"], "kind": "release"} for r in rels]
    return [{"repo": repo, "tag": t["name"], "date": commit_date(repo, t["commit"]["sha"]),
             "url": f"https://github.com/{repo}/releases/tag/{t['name']}", "kind": "tag"} for t in rest(f"/repos/{repo}/tags?per_page={min(n, 2)}")]


def upstream(login, own):
    """Merged pull requests to repositories outside the owner's own orgs."""
    q = f"is:pr is:merged author:{login} " + " ".join(f"-org:{o}" for o in own) + f" -user:{login}"
    prs, cursor = [], None
    while True:
        after = f', after:"{cursor}"' if cursor else ""
        d = gql(f"""{{search(type:ISSUE, first:100, query:{json.dumps(q)}{after}){{issueCount pageInfo{{hasNextPage endCursor}}
          nodes{{...on PullRequest{{mergedAt repository{{nameWithOwner stargazerCount url}}}}}}}}}}""")["search"]
        prs += d["nodes"]
        if not d["pageInfo"]["hasNextPage"]:
            break
        cursor = d["pageInfo"]["endCursor"]
    repos = {}
    for pr in prs:
        r = pr["repository"]
        e = repos.setdefault(r["nameWithOwner"], {"repo": r["nameWithOwner"], "stars": r["stargazerCount"], "url": r["url"], "prs": 0, "first": pr["mergedAt"], "last": pr["mergedAt"]})
        e["prs"] += 1
        e["first"] = min(e["first"], pr["mergedAt"])
        e["last"] = max(e["last"], pr["mergedAt"])
    return {"query": q, "merged": len(prs), "repos": sorted(repos.values(), key=lambda r: -r["stars"])}


def guarded(label, fn, fallback):
    try:
        return fn()
    except (urllib.error.URLError, RuntimeError, KeyError, ValueError, TimeoutError) as e:
        print(f"warn: {label}: {e}; keeping previous value {fallback}", file=sys.stderr)
        return fallback


def run(root):
    global TOKEN
    TOKEN = token()
    cfg = json.load(open(os.path.join(root, "tools/profile/config.json")))
    data_path = os.path.join(root, "data/profile.json")
    prev = json.load(open(data_path)) if os.path.exists(data_path) else {}
    prev_dl = prev.get("downloads", {})

    print("fetching user stats...", file=sys.stderr)
    out = {"fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "user": user_stats(cfg["login"])}

    prev_repos = prev.get("repos", {})
    repos = {}
    for p in cfg["projects"]:
        r = rest(f"/repos/{p['repo']}")
        print(f"fetching {p['repo']} ({r['stargazers_count']} stars)...", file=sys.stderr)
        repos[p["repo"]] = {
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "language": r["language"] or "",
            "description": p.get("description") or r["description"] or "",
            "created_at": r["created_at"],
            "url": r["html_url"],
            "history": star_history(p["repo"], r["stargazers_count"]),
            "dependents": guarded(f"dependents {p['repo']}", lambda: dependents(p["repo"]),
                                  prev_repos.get(p["repo"], {}).get("dependents", {"repositories": 0, "packages": 0})),
        }
    out["repos"] = repos

    print("fetching releases and upstream contributions...", file=sys.stderr)
    feed = [r for p in cfg["projects"] for r in releases(p["repo"])]
    out["releases"] = sorted(feed, key=lambda r: r["date"], reverse=True)[:10]
    out["upstream"] = upstream(cfg["login"], cfg["own_orgs"])

    dl = cfg["downloads"]
    out["downloads"] = {
        "docker_hub": guarded("docker hub", lambda: docker_pulls(dl["docker_hub"]), prev_dl.get("docker_hub", 0)),
        "ghcr": guarded("ghcr", lambda: ghcr_downloads(dl["ghcr"]), prev_dl.get("ghcr", 0)),
        "github_releases": guarded("releases", lambda: sum(release_downloads(r) for r in dl["github_releases"]), prev_dl.get("github_releases", 0)),
    }

    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    with open(data_path, "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")

    # Daily snapshots so download/star trends can be charted once enough history accrues.
    hist_path = os.path.join(root, "data/history.json")
    hist = json.load(open(hist_path)) if os.path.exists(hist_path) else []
    today = out["fetched_at"][:10]
    hist = [h for h in hist if h["date"] != today]
    hist.append({"date": today, "downloads": out["downloads"], "stars": {k: v["stars"] for k, v in repos.items()}})
    with open(hist_path, "w") as f:
        json.dump(hist, f, indent=1)
        f.write("\n")
    print(f"wrote {data_path}", file=sys.stderr)
