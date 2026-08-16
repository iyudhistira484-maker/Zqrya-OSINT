"""Auto-chaining: jika ditemukan email/phone, tawarkan scan lanjutan."""
import re
from stalker.reporters import terminal as term

async def ask_follow_up(result: dict, original_input: str) -> dict:
    """Periksa hasil, tawarkan scan tambahan jika ada entitas baru (cegah infinite loop)."""
    summary = result.get("summary", {})
    found_email = None
    found_phone = None

    # Cari email dari text_entities
    entities = summary.get("text_entities", [])
    for ent in entities:
        if "@" in ent and "." in ent.split("@")[-1]:
            found_email = ent
            break

    # Cari phone dari text_entities atau result scan
    for ent in entities:
        if re.match(r"^\+?[0-9]{7,15}$", ent.replace(" ", "").replace("-", "")):
            found_phone = ent
            break
            
    if not found_phone and summary.get("phone_registered", 0) > 0:
        phone_scan = result.get("phone_scan", [])
        for p in phone_scan:
            if p.get("phone"):
                found_phone = p["phone"]
                break

    # Tawarkan (pastikan tidak mengulang input asli untuk mencegah infinite loop)
    if found_email and found_email.lower() != original_input.lower():
        ans = input(f"\n  📧 Ditemukan email: {found_email}. Lakukan investigasi email? (y/n): ").strip().lower()
        if ans in ("y", "yes"):
            import stalker.menu as menu # Local import untuk mencegah Circular Import Crash
            await menu._run_email_full(found_email)
            
    if found_phone and found_phone.replace("+", "") != original_input.replace("+", ""):
        ans = input(f"\n  📱 Ditemukan nomor: {found_phone}. Lakukan investigasi nomor telepon? (y/n): ").strip().lower()
        if ans in ("y", "yes"):
            import stalker.menu as menu # Local import untuk mencegah Circular Import Crash
            await menu._run_phone_full(found_phone)
            
    return result
