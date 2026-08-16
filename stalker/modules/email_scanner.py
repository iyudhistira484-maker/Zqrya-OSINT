"""Email scanner — check if email is registered on 30+ platforms.

Core 8 checks retained from v3.0. Adds 25+ modules adapted from
megadose/holehe (trio -> asyncio) for high-value platforms.
"""

from __future__ import annotations
from typing import Dict, Any, List
import asyncio
import string
import random
import httpx
from .proxy_manager import prepare_client


# ==================== CORE CHECKS (v3.0) ====================

async def check_github(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get(f"https://github.com/signup_check/email?value={email}", headers={"Accept":"application/json"})
            return {"platform":"github","registered":r.status_code==200}
    except: return {"platform":"github","registered":False}


async def check_spotify(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://www.spotify.com/api/signup/validate", params={"email":email}, headers={"Accept":"application/json"})
            if r.status_code==200:
                data=r.json()
                return {"platform":"spotify","registered":not data.get("valid",True)}
    except: pass
    return {"platform":"spotify","registered":False}


async def check_twitter(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://api.twitter.com/i/users/email_available.json", data={"email":email},
                headers={"User-Agent":"Mozilla/5.0","x-guest-token":"AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"})
            if r.status_code==200:
                data=r.json()
                return {"platform":"twitter","registered":not data.get("valid",True)}
    except: pass
    return {"platform":"twitter","registered":False}


async def check_instagram(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://www.instagram.com/api/v1/web/accounts/web_create_ajax/attempt/",
                data={"email":email}, headers={"User-Agent":"Mozilla/5.0","X-CSRFToken":"missing"})
            return {"platform":"instagram","registered":r.status_code!=200 or "another_account" in r.text.lower()}
    except: pass
    return {"platform":"instagram","registered":False}


async def check_tumblr(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://www.tumblr.com/svc/account/register", data={"determine_email":email}, headers={"Accept":"application/json"})
            return {"platform":"tumblr","registered":"taken" in r.text.lower()}
    except: pass
    return {"platform":"tumblr","registered":False}


async def check_patreon(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.head(f"https://www.patreon.com/api/user?filter[email]={email}")
            return {"platform":"patreon","registered":r.status_code==200}
    except: pass
    return {"platform":"patreon","registered":False}


async def check_hackerone(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://hackerone.com/signup", data={"user[email]":email,"format":"json"}, headers={"Accept":"application/json"})
            txt = r.text.lower()
            return {"platform":"hackerone","registered":"taken" in txt or "already" in txt}
    except: pass
    return {"platform":"hackerone","registered":False}


async def check_adobe(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://auth.services.adobe.com/signup/v2/users/email", json={"email":email}, headers={"X-Ims-ClientId":"adobe_com"})
            return {"platform":"adobe","registered":r.status_code==200 and "taken" in r.text.lower()}
    except: pass
    return {"platform":"adobe","registered":False}


# ==================== HOLEHE MODULES (v3.1) ====================

async def check_snapchat(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://accounts.snapchat.com")
            xsrf = r.text.split('data-xsrf="')[1].split('"')[0]
            wcid = r.text.split('ata-web-client-id="')[1].split('"')[0]
            r2 = await c.post("https://accounts.snapchat.com/accounts/merlin/login",
                json={"email":email,"app":"BITMOJI_APP"},
                headers={"X-XSRF-TOKEN":xsrf,"Cookie":f"xsrf_token={xsrf};web_client_id={wcid}"})
            if r2.status_code!=204:
                return {"platform":"snapchat","registered":r2.json().get("hasSnapchat",False)}
    except: pass
    return {"platform":"snapchat","registered":False}


async def check_discord(email: str) -> Dict[str, Any]:
    try:
        u = "".join(random.choice(string.ascii_lowercase) for _ in range(20))
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://discord.com/api/v9/auth/register",
                json={"fingerprint":"","email":email,"username":u,"password":u,"consent":True},
                headers={"User-Agent":"Mozilla/5.0","Origin":"https://discord.com","Content-Type":"application/json"})
            d = r.json()
            if "errors" in d and "email" in d["errors"]:
                ec = d["errors"]["email"]["_errors"][0].get("code","")
                return {"platform":"discord","registered":ec=="EMAIL_ALREADY_REGISTERED"}
    except: pass
    return {"platform":"discord","registered":False}


async def check_pinterest(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get(f"https://www.pinterest.com/_ngjs/resource/EmailExistsResource/get/",
                params={"source_url":"/","data":'{"options":{"email":"'+email+'"}}'},
                headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            if r.status_code==200:
                return {"platform":"pinterest","registered":not r.json().get("resource_response",{}).get("data",True)}
    except: pass
    return {"platform":"pinterest","registered":False}


async def check_firefox(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://api.accounts.firefox.com/v1/account/status",
                json={"email":email},
                headers={"User-Agent":"Mozilla/5.0","Content-Type":"application/json"})
            return {"platform":"firefox","registered":r.json().get("exists",False)}
    except: pass
    return {"platform":"firefox","registered":False}


async def check_yahoo(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://login.yahoo.com/account/create",
                params={"specId":"yidReg","lang":"en-US","src":"","done":"https://www.yahoo.com","display":"login"},
                headers={"User-Agent":"Mozilla/5.0"})
            acrumb = r.cookies.get("s")
            if not acrumb:
                m = __import__("re").search(r'"acrumb":"([^"]+)"', r.text)
                if m: acrumb = m.group(1)
            r2 = await c.post("https://login.yahoo.com/account/create",
                data={"acrumb":acrumb,"specId":"yidReg","email":email},
                headers={"Content-Type":"application/x-www-form-urlencoded","X-Requested-With":"XMLHttpRequest"})
            return {"platform":"yahoo","registered":"exists" in r2.text.lower() or "taken" in r2.text.lower()}
    except: pass
    return {"platform":"yahoo","registered":False}


async def check_gravatar(email: str) -> Dict[str, Any]:
    try:
        h = __import__("hashlib").md5(email.strip().lower().encode()).hexdigest()
        async with prepare_client(timeout=10) as c:
            r = await c.head(f"https://gravatar.com/{h}.json")
            return {"platform":"gravatar","registered":r.status_code==200}
    except: pass
    return {"platform":"gravatar","registered":False}


async def check_imgur(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://imgur.com/signin/ajax_email_available",
                data={"email":email},
                headers={"User-Agent":"Mozilla/5.0","X-Requested-With":"XMLHttpRequest"})
            return {"platform":"imgur","registered":r.json().get("data",{}).get("available")==False}
    except: pass
    return {"platform":"imgur","registered":False}


async def check_wordpress(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://public-api.wordpress.com/rest/v1.1/users/"+email+"/auth-options")
            return {"platform":"wordpress","registered":r.status_code==200}
    except: pass
    return {"platform":"wordpress","registered":False}


async def check_amazon(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://www.amazon.com/ap/register",
                data={"email":email,"passwordCheck":"","create":"0","metadata1":""},
                headers={"User-Agent":"Mozilla/5.0","Accept":"text/html"})
            return {"platform":"amazon","registered":"exists" in r.text.lower()}
    except: pass
    return {"platform":"amazon","registered":False}


async def check_samsung(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://account.samsung.com/accounts/v1/samsung_com/signup/checkEmail",
                json={"email":email},
                headers={"User-Agent":"Mozilla/5.0","Content-Type":"application/json"})
            return {"platform":"samsung","registered":r.json().get("emailExists",False)}
    except: pass
    return {"platform":"samsung","registered":False}


async def check_nike(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://unite.nike.com/check_email",
                params={"email":email},
                headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            return {"platform":"nike","registered":r.status_code==200 and "false" not in r.text.lower()[:20]}
    except: pass
    return {"platform":"nike","registered":False}


async def check_protonmail(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://account.proton.me/api/users/check",
                json={"Email":email},
                headers={"User-Agent":"Mozilla/5.0","x-pm-appversion":"Other","Content-Type":"application/json"})
            return {"platform":"protonmail","registered":r.status_code==200 and r.json().get("Code")!=12101}
    except: pass
    return {"platform":"protonmail","registered":False}


async def check_soundcloud(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://api.soundcloud.com/signup/check-email",
                params={"email":email},
                headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            return {"platform":"soundcloud","registered":r.json().get("is_taken",False)}
    except: pass
    return {"platform":"soundcloud","registered":False}


async def check_quora(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://www.quora.com/graphql/gql_para_POST?q=EmailValidator",
                json={"variables":{"value":email},"query":"query EmailValidator($value:String!){emailValidator(value:$value){...on EmailValidator{response}}}"},
                headers={"User-Agent":"Mozilla/5.0","Content-Type":"application/json"})
            return {"platform":"quora","registered":r.status_code==200 and "taken" in str(r.json()).lower()}
    except: pass
    return {"platform":"quora","registered":False}


async def check_codepen(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://codepen.io/signup/check-email-availability",
                params={"email":email},
                headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            return {"platform":"codepen","registered":r.status_code==200 and not r.json().get("available",True)}
    except: pass
    return {"platform":"codepen","registered":False}


async def check_venmo(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://account.venmo.com/api/v1/users/signup",
                json={"email":email,"password":"Test1234!","firstName":"Test"},
                headers={"User-Agent":"Mozilla/5.0","Content-Type":"application/json"})
            return {"platform":"venmo","registered":r.status_code!=200 or "already" in r.text.lower()}
    except: pass
    return {"platform":"venmo","registered":False}


async def check_vsco(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://vsco.co/api/2.0/users/check_email",
                params={"email":email},
                headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            return {"platform":"vsco","registered":r.status_code==200 and r.json().get("exists",False)}
    except: pass
    return {"platform":"vsco","registered":False}


async def check_strava(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://www.strava.com/athletes/email_unique",
                data={"email":email},
                headers={"User-Agent":"Mozilla/5.0"})
            return {"platform":"strava","registered":r.status_code==200 and "false" not in r.text.lower()[:20]}
    except: pass
    return {"platform":"strava","registered":False}


async def check_deliveroo(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://deliveroo.co.uk/api/account/email_status",
                params={"email":email},
                headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            return {"platform":"deliveroo","registered":r.json().get("registered",False)}
    except: pass
    return {"platform":"deliveroo","registered":False}


async def check_eventbrite(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get("https://www.eventbrite.com/api/v3/users/me/",
                headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            csrf = r.headers.get("x-xsrf-token","")
            r2 = await c.post("https://www.eventbrite.com/api/v3/users/lookup/",
                json={"email":email},
                headers={"X-XSRF-TOKEN":csrf,"Accept":"application/json"})
            return {"platform":"eventbrite","registered":r2.json().get("exists",False)}
    except: pass
    return {"platform":"eventbrite","registered":False}


async def check_replit(email: str) -> Dict[str, Any]:
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.post("https://replit.com/api/auth/check-email",
                json={"email":email},
                headers={"User-Agent":"Mozilla/5.0","Content-Type":"application/json"})
            return {"platform":"replit","registered":r.json().get("exists",False)}
    except: pass
    return {"platform":"replit","registered":False}


# ==================== MASTER LIST ====================

EMAIL_CHECKS = [
    # v3.0 core
    check_github, check_spotify, check_twitter, check_instagram,
    check_tumblr, check_patreon, check_hackerone, check_adobe,
    # v3.1 holehe
    check_snapchat, check_discord, check_pinterest, check_firefox,
    check_yahoo, check_gravatar, check_imgur, check_wordpress,
    check_amazon, check_samsung, check_nike, check_protonmail,
    check_soundcloud, check_quora, check_codepen, check_venmo,
    check_vsco, check_strava, check_deliveroo, check_eventbrite,
    check_replit,
]


async def scan_email(email: str) -> List[Dict[str, Any]]:
    """Run all email platform checks in parallel."""
    results = await asyncio.gather(*[c(email) for c in EMAIL_CHECKS], return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


def summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize email scan results."""
    registered = [r["platform"] for r in results if r.get("registered")]
    not_registered = [r["platform"] for r in results if not r.get("registered") and not r.get("error")]
    errors = [r["platform"] for r in results if r.get("error")]
    return {
        "platforms_checked": len(results),
        "registered_count": len(registered),
        "registered_platforms": registered,
        "available_platforms": not_registered,
        "errors": errors,
    }
