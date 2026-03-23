import re
import unicodedata
from typing import Any, Dict, List

from app.services.guidance_taxonomy import DOMAIN_KEYWORDS, TRACK_KEYWORDS


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def guidance_text(item: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(item.get("name", "")),
            str(item.get("university", "")),
            str(item.get("field", "")),
            str(item.get("description", "")),
            str(item.get("career_paths", "")),
        ]
    ).lower()


def infer_domains(item: Dict[str, Any]) -> List[str]:
    existing = item.get("domains") or []
    if existing:
        return [str(domain).strip().lower() for domain in existing if str(domain).strip()]

    text = guidance_text(item)
    folded = _fold(text)

    domains = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        matched = False
        for keyword in keywords:
            kw_lower = keyword.lower()
            kw_folded = _fold(keyword)
            pattern = rf"\b{re.escape(kw_lower)}\b"
            pattern_folded = rf"\b{re.escape(kw_folded)}\b"
            if re.search(pattern, text) or re.search(pattern_folded, folded):
                matched = True
                break
        if matched:
            domains.append(domain)
    return domains or ["other"]


def infer_tracks(item: Dict[str, Any], domains: List[str]) -> List[str]:
    existing = item.get("tracks") or []
    if existing:
        return [str(track).strip().lower() for track in existing if str(track).strip()]

    text = guidance_text(item)
    folded = _fold(text)
    tracks: List[str] = []
    for domain in domains:
        for track, keywords in TRACK_KEYWORDS.get(domain, {}).items():
            matched = False
            for keyword in keywords:
                kw_lower = keyword.lower()
                kw_folded = _fold(keyword)
                pattern = rf"\b{re.escape(kw_lower)}\b"
                pattern_folded = rf"\b{re.escape(kw_folded)}\b"
                if re.search(pattern, text) or re.search(pattern_folded, folded):
                    matched = True
                    break
            if matched:
                tracks.append(track)

    deduped = []
    seen = set()
    for track in tracks:
        if track in seen:
            continue
        seen.add(track)
        deduped.append(track)
    return deduped


def annotate_guidance_item(item: Dict[str, Any]) -> Dict[str, Any]:
    annotated = dict(item)
    domains = infer_domains(annotated)
    annotated["domains"] = domains
    annotated["tracks"] = infer_tracks(annotated, domains)
    return annotated
