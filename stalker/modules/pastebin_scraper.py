"""Pastebin & JustPaste.it leak check via Google dork."""
import re
from stalker.reporters import terminal as term

async def search_pastebin(query: str) -> list:
    """Cari di pastebin.com dan justpaste.it menggunakan Google dork."""
    results = []
    dorks = [
        f'site:pastebin.com "{query}"',
        f'site:justpaste.it "{query}"',
    ]
    try:
        from googlesearch import search
    except ImportError:
        term.print_error("googlesearch not installed. Install: pip install googlesearch-python")
        return results
    for dork in dorks:
        try:
            for url in search(dork, num_results=10, stop=10):
                results.append(url)
        except Exception as e:
            term.print_warning(f"Google search error for {dork}: {e}")
    return results

async def pastebin_scan(query: str) -> dict:
    """Main entry."""
    term.print_phase(1, "Pastebin Scan", f"Searching pastebin for {query}...")
    urls = await search_pastebin(query)
    return {"query": query, "urls": urls, "count": len(urls)}
