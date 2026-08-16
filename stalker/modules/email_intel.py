"""Advanced Email Intelligence Module.

Features (all free, no API key):
- Google account checker (does email have Google/Gmail account?)
- Microsoft/Outlook account detection
- Proton Mail account detection
- Disposable email detection (known temp-mail domains)
- MX record lookup (find email provider)
- SMTP deliverability check (is mailbox active?)
- Email reputation: age estimation, pattern analysis
- Extract username from email local-part
- Detect email format patterns (firstname.lastname, etc.)
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import asyncio, re, socket
from .proxy_manager import prepare_client

DISPOSABLE_DOMAINS = {
    "mailinator.com","guerrillamail.com","10minutemail.com","tempmail.com",
    "throwaway.email","yopmail.com","sharklasers.com","guerrillamailblock.com",
    "grr.la","guerrillamail.info","spam4.me","trashmail.com","trashmail.me",
    "dispostable.com","maildrop.cc","spamgourmet.com","mytemp.email",
    "fakeinbox.com","getairmail.com","mailnull.com","spamspot.com",
    "tempr.email","discard.email","spamevade.com","boun.cr",
}

EMAIL_PATTERNS = {
    "firstname.lastname": re.compile(r'^[a-z]+\.[a-z]+$'),
    "firstname_lastname": re.compile(r'^[a-z]+_[a-z]+$'),
    "firstname+year": re.compile(r'^[a-z]+(19|20)\d{2}$'),
    "initials": re.compile(r'^[a-z]{1,3}\d{2,4}$'),
    "random": re.compile(r'^[a-z0-9]{8,}$'),
}

async def check_google_account(email: str) -> Dict[str, Any]:
    """Detect if email has a Google account (via account recovery flow)."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.post(
                "https://accounts.google.com/_/signin/sl/lookup",
                data={"f.req": f'["{email}",null,true]', "continue": "https://myaccount.google.com"},
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"},
            )
            exists = r.status_code == 200 and "gaia" in r.text.lower()
            # More reliable: check via lookup
            r2 = await c.post(
                "https://accounts.google.com/v3/signin/_/AccountsSignInUi/data/batchexecute",
                data={"f.req": f'[[["79DCYEb8ME","[\\"1\\",null,null,null,null,\\"2\\",null,null,null,\\"3\\",null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,\\"' + email + '\\"\\"]",null,"generic"]]]'},
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"},
            )
            account_exists = '"ACCOUNT_LOOKUP"' in r2.text if r2.status_code == 200 else False
            return {"platform": "google", "exists": account_exists or exists, "method": "account_lookup"}
    except Exception as e:
        return {"platform": "google", "exists": False, "error": str(e)}

async def check_microsoft_account(email: str) -> Dict[str, Any]:
    """Detect Microsoft/Outlook/Hotmail account."""
    try:
        async with prepare_client(timeout=15) as c:
            r = await c.post(
                "https://login.live.com/GetCredentialType.srf",
                json={"username": email, "isOtherIdpSupported": True, "checkPhones": False,
                      "isRemoteNGCSupported": True, "isCookieBannerShown": False, "isFidoSupported": False},
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            )
            if r.status_code == 200:
                d = r.json()
                # IfExistsResult: 0 = not found, 1 = exists, 5 = throttled
                exists = d.get("IfExistsResult", 0) == 1
                is_federated = d.get("EstsProperties", {}).get("UserTenantBranding") is not None
                return {"platform": "microsoft", "exists": exists, "federated": is_federated}
    except Exception as e:
        return {"platform": "microsoft", "exists": False, "error": str(e)}
    return {"platform": "microsoft", "exists": False}

async def check_protonmail(email: str) -> Dict[str, Any]:
    """Detect ProtonMail account."""
    local = email.split("@")[0]
    try:
        async with prepare_client(timeout=10) as c:
            r = await c.get(
                f"https://api.protonmail.ch/pks/lookup?op=index&search={local}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            exists = r.status_code == 200 and local.lower() in r.text.lower()
            return {"platform": "protonmail", "exists": exists}
    except Exception as e:
        return {"platform": "protonmail", "exists": False, "error": str(e)}

async def get_mx_records(domain: str) -> List[str]:
    """Get MX records to identify email provider."""
    try:
        loop = asyncio.get_event_loop()
        import dns.resolver
        result = await loop.run_in_executor(None, lambda: dns.resolver.resolve(domain, 'MX'))
        return sorted([str(r.exchange).rstrip('.') for r in result])
    except ImportError:
        # Fallback: basic socket lookup
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, socket.getaddrinfo, domain, 25)
            return [domain] if result else []
        except Exception:
            return []
    except Exception:
        return []

async def smtp_verify(email: str) -> Dict[str, Any]:
    """Check if email mailbox exists via SMTP VRFY (non-invasive)."""
    domain = email.split("@")[-1]
    try:
        import smtplib
        loop = asyncio.get_event_loop()
        def _check():
            try:
                with smtplib.SMTP(domain, 25, timeout=8) as s:
                    s.helo("check.local")
                    code, _ = s.verify(email)
                    return {"smtp_verified": code == 250, "code": code}
            except Exception as ex:
                return {"smtp_verified": None, "error": str(ex)[:50]}
        return await loop.run_in_executor(None, _check)
    except Exception as e:
        return {"smtp_verified": None, "error": str(e)}

def is_disposable(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    return domain in DISPOSABLE_DOMAINS

def detect_pattern(local: str) -> str:
    """Detect email local-part naming pattern."""
    for name, pattern in EMAIL_PATTERNS.items():
        if pattern.match(local.lower()):
            return name
    return "custom"

def identify_provider(domain: str) -> str:
    PROVIDERS = {
        "gmail.com": "Google Gmail", "googlemail.com": "Google Gmail",
        "yahoo.com": "Yahoo Mail", "yahoo.co.id": "Yahoo Mail (ID)",
        "hotmail.com": "Microsoft Hotmail", "outlook.com": "Microsoft Outlook",
        "live.com": "Microsoft Live", "protonmail.com": "ProtonMail",
        "proton.me": "ProtonMail", "icloud.com": "Apple iCloud",
        "me.com": "Apple iCloud", "yandex.com": "Yandex Mail",
        "yandex.ru": "Yandex Mail", "tutanota.com": "Tutanota",
        "zoho.com": "Zoho Mail", "aol.com": "AOL Mail",
    }
    return PROVIDERS.get(domain.lower(), f"Custom ({domain})")

async def full_email_intel(email: str) -> Dict[str, Any]:
    """Full email intelligence pipeline."""
    domain = email.split("@")[-1]
    local = email.split("@")[0]

    disposable = is_disposable(email)
    provider = identify_provider(domain)
    pattern = detect_pattern(local)

    # Run platform checks in parallel
    tasks = [check_microsoft_account(email)]
    if domain in ("gmail.com", "googlemail.com"):
        tasks.append(check_google_account(email))
    if domain in ("protonmail.com", "proton.me"):
        tasks.append(check_protonmail(email))

    platform_results = await asyncio.gather(*tasks, return_exceptions=True)
    platforms = {r["platform"]: r for r in platform_results if isinstance(r, dict) and "platform" in r}

    return {
        "email": email,
        "domain": domain,
        "local_part": local,
        "provider": provider,
        "is_disposable": disposable,
        "naming_pattern": pattern,
        "platforms": platforms,
        "username_clue": local,
    }

def summary(data: Dict[str, Any]) -> Dict[str, Any]:
    platforms_found = [p for p, d in data.get("platforms", {}).items() if d.get("exists")]
    return {
        "email": data.get("email",""),
        "provider": data.get("provider",""),
        "is_disposable": data.get("is_disposable", False),
        "naming_pattern": data.get("naming_pattern",""),
        "account_on": platforms_found,
        "username_clue": data.get("username_clue",""),
    }
