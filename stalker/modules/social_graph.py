"""Social Network Graph — map relationships and find associates.

From target's social media:
- Extract followers/following on Reddit (mutual subreddits = community)
- GitHub: find who stars/forks target's repos
- Find accounts that frequently interact (reply/mention)
- Build adjacency list of known associates
- Identify hub accounts (high interaction = close associate)
- Detect community clusters (same subreddits/orgs)

All via public APIs — no authentication needed.
"""
from __future__ import annotations
from typing import Dict, Any, List, Set
import asyncio
from collections import Counter
from .proxy_manager import prepare_client

GH_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"}
RD_HEADERS = {"User-Agent": "Zqrya/3.0 OSINT"}

async def get_github_network(username: str) -> Dict[str, Any]:
    """Get GitHub followers/following + stargazers of repos."""
    async with prepare_client(timeout=15, headers=GH_HEADERS) as c:
        async def _get(url):
            try:
                r = await c.get(url)
                return r.json() if r.status_code == 200 else []
            except Exception: return []

        followers, following, repos = await asyncio.gather(
            _get(f"https://api.github.com/users/{username}/followers?per_page=20"),
            _get(f"https://api.github.com/users/{username}/following?per_page=20"),
            _get(f"https://api.github.com/users/{username}/repos?per_page=10&sort=stars"),
        )

        follower_names = [u.get("login","") for u in (followers if isinstance(followers,list) else [])[:20]]
        following_names = [u.get("login","") for u in (following if isinstance(following,list) else [])[:20]]
        mutual = list(set(follower_names) & set(following_names))

        # Stargazers of top repo
        top_stargazers = []
        if isinstance(repos, list) and repos:
            top_repo = repos[0].get("name","")
            if top_repo:
                sg = await _get(f"https://api.github.com/repos/{username}/{top_repo}/stargazers?per_page=10")
                top_stargazers = [u.get("login","") for u in (sg if isinstance(sg,list) else [])[:10]]

        return {
            "followers": follower_names,
            "following": following_names,
            "mutual_connections": mutual,
            "top_stargazers": top_stargazers,
            "total_followers": len(follower_names),
            "total_following": len(following_names),
        }

async def get_reddit_community(username: str) -> Dict[str, Any]:
    """Find Reddit users who interact with target in same subreddits."""
    async with prepare_client(timeout=15, headers=RD_HEADERS) as c:
        try:
            r = await c.get(f"https://www.reddit.com/user/{username}/comments.json?limit=20&sort=new")
            if r.status_code != 200: return {}
            comments = r.json().get("data",{}).get("children",[])
            subreddits = [c_["data"].get("subreddit","") for c_ in comments]
            top_subs = [s for s,_ in Counter(subreddits).most_common(5)]

            # Find other active users in same subreddits
            community_users: Counter = Counter()
            async def _check_sub(sub):
                try:
                    rr = await c.get(f"https://www.reddit.com/r/{sub}/new.json?limit=10",
                                    headers=RD_HEADERS)
                    if rr.status_code == 200:
                        posts = rr.json().get("data",{}).get("children",[])
                        for p in posts:
                            author = p.get("data",{}).get("author","")
                            if author and author not in ("[deleted]",username,"AutoModerator"):
                                community_users[author] += 1
                except Exception: pass

            await asyncio.gather(*[_check_sub(s) for s in top_subs[:3]], return_exceptions=True)
            return {
                "top_subreddits": top_subs,
                "community_members": community_users.most_common(10),
            }
        except Exception: return {}

async def full_social_graph(result: Dict[str, Any]) -> Dict[str, Any]:
    username = result.get("username","")
    if not username: return {"note": "username required for social graph"}

    gh_net, rd_community = await asyncio.gather(
        get_github_network(username), get_reddit_community(username),
        return_exceptions=True)

    return {
        "github_network": gh_net if isinstance(gh_net, dict) else {},
        "reddit_community": rd_community if isinstance(rd_community, dict) else {},
    }

def format_social_graph(data: Dict[str, Any]) -> str:
    BOLD="\033[1m"; CYAN="\033[36m"; YELLOW="\033[33m"; GREEN="\033[32m"; NC="\033[0m"
    lines=[f"\n{BOLD}  ┌─── SOCIAL NETWORK GRAPH ───┐{NC}"]
    gh=data.get("github_network",{})
    if gh:
        lines.append(f"  GitHub: {gh.get('total_followers',0)} followers / {gh.get('total_following',0)} following")
        if gh.get("mutual_connections"):
            lines.append(f"  {GREEN}Mutual connections:{NC} {', '.join(gh['mutual_connections'][:8])}")
        if gh.get("top_stargazers"):
            lines.append(f"  Top stargazers: {', '.join(gh['top_stargazers'][:6])}")
    rd=data.get("reddit_community",{})
    if rd:
        lines.append(f"\n  Reddit communities: {', '.join(rd.get('top_subreddits',[])[:5])}")
        if rd.get("community_members"):
            users=[u for u,_ in rd["community_members"][:5]]
            lines.append(f"  {YELLOW}Frequent co-members:{NC} {', '.join(users)}")
    return "\n".join(lines)
