"""WHOIS lookup for email domain."""
import whois
import re
from stalker.reporters import terminal as term

async def check_domain(email: str) -> dict:
    """Ekstrak domain dari email, lakukan WHOIS."""
    domain = email.split("@")[-1] if "@" in email else None
    if not domain:
        return {"error": "Invalid email"}
    term.print_phase(1, "WHOIS Check", f"Looking up {domain}...")
    try:
        w = whois.whois(domain)
        info = {}
        for k, v in w.items():
            if v:
                info[k] = str(v)
        return {"domain": domain, "whois": info}
    except Exception as e:
        return {"domain": domain, "error": str(e)}
