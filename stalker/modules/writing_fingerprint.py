"""Writing Style Fingerprinting — identify same author across accounts.

Analyzes linguistic patterns to determine if two different accounts
are operated by the same person. Useful when:
- Suspect has created fake accounts
- Target uses different usernames across platforms
- Need to link anonymous account to known identity

Features:
- Vocabulary richness (TTR - Type Token Ratio)
- Average sentence/word length
- Punctuation habits (!!!???... overuse)
- Common word/phrase patterns
- Language detection (Indonesian vs English mix)
- Capitalization habits (ALL CAPS, camelCase, no caps)
- Emoji usage patterns
- Similarity score between two text samples

No API needed — pure NLP analysis on collected text.
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import re
import math
from collections import Counter


def extract_text_samples(result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Pull all text samples from investigation."""
    samples = []

    # Reddit posts/comments
    reddit = result.get("reddit_intel", {})
    reddit_text = []
    for post in reddit.get("recent_posts", []):
        if post.get("title"): reddit_text.append(post["title"])
    for comment in reddit.get("recent_comments", []):
        if comment.get("body"): reddit_text.append(comment["body"])
    if reddit_text:
        samples.append({"source": "reddit", "text": " ".join(reddit_text)})

    # Bios from found sites
    bio_texts = []
    for site in result.get("maigret", {}).get("found_sites", []):
        bio = site.get("bio") or site.get("ids_data", {}).get("bio", "")
        if bio and len(bio) > 20:
            bio_texts.append(bio)
    if bio_texts:
        samples.append({"source": "social_bios", "text": " ".join(bio_texts)})

    # Telegram bio
    tg = result.get("telegram", {})
    if tg.get("bio") and len(tg["bio"]) > 10:
        samples.append({"source": "telegram_bio", "text": tg["bio"]})

    # Custom APIs bios
    for platform, data in result.get("custom_apis", {}).items():
        if isinstance(data, dict) and data.get("bio") and len(data["bio"]) > 20:
            samples.append({"source": f"{platform}_bio", "text": data["bio"]})

    return samples


def analyze_text(text: str) -> Dict[str, Any]:
    """Deep linguistic analysis of a text sample."""
    if not text or len(text) < 30:
        return {}

    # Tokenize
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not words:
        return {}

    unique_words = set(words)
    word_freq = Counter(words)

    # === Core Metrics ===
    ttr = len(unique_words) / len(words)  # Type-Token Ratio (vocabulary richness)
    avg_word_len = sum(len(w) for w in words) / len(words)
    avg_sent_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

    # === Punctuation habits ===
    exclamation_density = text.count("!") / max(len(sentences), 1)
    question_density = text.count("?") / max(len(sentences), 1)
    ellipsis_usage = text.count("...") + text.count("…")
    comma_density = text.count(",") / max(len(words), 1)

    # === Capitalization ===
    all_caps_words = len(re.findall(r'\b[A-Z]{2,}\b', text))
    no_caps_ratio = len(re.findall(r'^[a-z]', text, re.M)) / max(len(sentences), 1)

    # === Emoji ===
    emoji_count = len(re.findall(
        r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
        r'\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+',
        text, re.UNICODE
    ))

    # === Language detection ===
    id_words = {"aku","saya","kamu","lo","gue","ini","itu","yang","dan","di","ke",
                "untuk","dengan","tidak","bisa","mau","udah","sudah","juga","dari","ada"}
    id_count = sum(1 for w in words if w in id_words)
    language = "Indonesian" if id_count > len(words) * 0.1 else \
               "Mixed" if id_count > len(words) * 0.03 else "English"

    # === Common phrases (top bigrams) ===
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
    top_bigrams = [bg for bg, _ in Counter(bigrams).most_common(5)]

    # === Top words (excluding stopwords) ===
    stopwords = {"the","a","an","is","are","was","were","be","been","has","have",
                 "had","do","does","did","will","would","could","should","may","might",
                 "i","you","he","she","it","we","they","dan","yang","di","ke","itu","ini"}
    meaningful_words = [w for w in word_freq.keys() if w not in stopwords and len(w) > 2]
    top_words = meaningful_words[:10]

    return {
        "word_count": len(words),
        "unique_words": len(unique_words),
        "vocabulary_richness_ttr": round(ttr, 3),
        "avg_word_length": round(avg_word_len, 2),
        "avg_sentence_length": round(avg_sent_len, 1),
        "exclamation_density": round(exclamation_density, 3),
        "question_density": round(question_density, 3),
        "ellipsis_count": ellipsis_usage,
        "all_caps_words": all_caps_words,
        "no_caps_ratio": round(no_caps_ratio, 3),
        "emoji_count": emoji_count,
        "language": language,
        "id_word_ratio": round(id_count / max(len(words), 1), 3),
        "top_words": top_words,
        "top_bigrams": top_bigrams,
        "comma_density": round(comma_density, 3),
    }


def compare_fingerprints(fp1: Dict, fp2: Dict) -> Dict[str, Any]:
    """Compare two writing fingerprints → similarity score 0-100."""
    if not fp1 or not fp2:
        return {"similarity": 0, "verdict": "insufficient data"}

    scores = []

    def metric_sim(k: str, tolerance: float = 0.2) -> float:
        v1, v2 = fp1.get(k), fp2.get(k)
        if v1 is None or v2 is None: return 0.5  # neutral
        if v1 == 0 and v2 == 0: return 1.0
        diff = abs(v1 - v2) / max(abs(v1), abs(v2), 1e-9)
        return max(0, 1 - diff / tolerance)

    # Weight: vocabulary and word length are most stable fingerprints
    weights = [
        ("vocabulary_richness_ttr", 0.25),
        ("avg_word_length", 0.20),
        ("avg_sentence_length", 0.15),
        ("exclamation_density", 0.10),
        ("question_density", 0.10),
        ("comma_density", 0.05),
        ("no_caps_ratio", 0.05),
        ("id_word_ratio", 0.10),
    ]

    weighted_score = sum(metric_sim(k, 0.3) * w for k, w in weights)
    language_match = 1.0 if fp1.get("language") == fp2.get("language") else 0.3

    # Word overlap
    words1 = set(fp1.get("top_words", []))
    words2 = set(fp2.get("top_words", []))
    word_overlap = len(words1 & words2) / max(len(words1 | words2), 1)

    final_score = (weighted_score * 0.6 + language_match * 0.2 + word_overlap * 0.2) * 100
    final_score = min(100, max(0, final_score))

    if final_score >= 80:
        verdict = "VERY LIKELY SAME AUTHOR"
    elif final_score >= 65:
        verdict = "PROBABLY SAME AUTHOR"
    elif final_score >= 50:
        verdict = "POSSIBLY SAME AUTHOR"
    elif final_score >= 35:
        verdict = "UNLIKELY SAME AUTHOR"
    else:
        verdict = "DIFFERENT AUTHORS"

    return {
        "similarity_score": round(final_score, 1),
        "verdict": verdict,
        "language_match": fp1.get("language") == fp2.get("language"),
        "shared_words": list(words1 & words2)[:5],
        "metric_details": {k: round(metric_sim(k, 0.3) * 100) for k, _ in weights},
    }


def full_writing_fingerprint(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build full writing fingerprint from all collected text."""
    samples = extract_text_samples(result)
    if not samples:
        return {"samples": 0, "note": "No text samples available"}

    fingerprints = {}
    for sample in samples:
        fp = analyze_text(sample["text"])
        if fp:
            fingerprints[sample["source"]] = fp

    # If multiple sources, compare them (consistency check)
    comparisons = []
    sources = list(fingerprints.keys())
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            cmp = compare_fingerprints(fingerprints[sources[i]], fingerprints[sources[j]])
            cmp["source_a"] = sources[i]
            cmp["source_b"] = sources[j]
            comparisons.append(cmp)

    # Aggregate fingerprint (average across sources)
    if fingerprints:
        all_fp = list(fingerprints.values())
        numeric_keys = [k for k, v in all_fp[0].items() if isinstance(v, (int, float))]
        aggregate = {k: round(sum(fp.get(k, 0) for fp in all_fp) / len(all_fp), 3)
                    for k in numeric_keys}
        aggregate["language"] = Counter(fp.get("language","") for fp in all_fp).most_common(1)[0][0]
    else:
        aggregate = {}

    return {
        "samples_analyzed": len(samples),
        "per_source": fingerprints,
        "aggregate": aggregate,
        "cross_platform_comparisons": comparisons,
    }


def format_fingerprint_report(data: Dict[str, Any]) -> str:
    BOLD = "\033[1m"; CYAN = "\033[36m"; YELLOW = "\033[33m"
    GREEN = "\033[32m"; RED = "\033[31m"; NC = "\033[0m"

    if not data.get("samples_analyzed"):
        return "  Writing Fingerprint: no text samples found"

    lines = [f"\n{BOLD}  ┌─── WRITING STYLE FINGERPRINT ───┐{NC}"]
    lines.append(f"  Analyzed {data['samples_analyzed']} text source(s)")

    agg = data.get("aggregate", {})
    if agg:
        lines.append(f"\n  {BOLD}Linguistic Profile:{NC}")
        lines.append(f"  Language:         {agg.get('language','')}")
        lines.append(f"  Vocabulary (TTR): {agg.get('vocabulary_richness_ttr',0)} "
                     f"({'rich' if agg.get('vocabulary_richness_ttr',0)>0.6 else 'limited'})")
        lines.append(f"  Avg word length:  {agg.get('avg_word_length',0)} chars")
        lines.append(f"  Avg sent length:  {agg.get('avg_sentence_length',0)} words")
        if agg.get("exclamation_density",0) > 1:
            lines.append(f"  {YELLOW}Exclamation heavy: {agg['exclamation_density']:.1f} per sentence{NC}")
        if agg.get("all_caps_words",0) > 3:
            lines.append(f"  {YELLOW}Frequent ALL CAPS usage{NC}")
        if agg.get("emoji_count",0) > 5:
            lines.append(f"  Emoji user: {agg['emoji_count']} emoji found")

    cmps = data.get("cross_platform_comparisons", [])
    if cmps:
        lines.append(f"\n  {BOLD}Cross-Platform Consistency:{NC}")
        for cmp in cmps:
            score = cmp["similarity_score"]
            color = GREEN if score >= 65 else YELLOW if score >= 45 else RED
            lines.append(f"  {cmp['source_a']} ↔ {cmp['source_b']}")
            lines.append(f"  → {color}{score}% match — {cmp['verdict']}{NC}")
            if cmp.get("shared_words"):
                lines.append(f"  → Shared vocab: {', '.join(cmp['shared_words'])}")

    return "\n".join(lines)
