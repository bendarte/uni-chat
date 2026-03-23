import re
import unicodedata
from typing import Iterable, List


TOPIC_ALIASES = {
    "artificial intelligence": {
        "ai",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "maskininlarning",
        "maskininlärning",
        "ml",
    },
    "computer science": {
        "computer science",
        "software engineering",
        "software development",
        "programming",
        "programmering",
        "datavetenskap",
        "informatics",
        "it",
        "information technology",
        "informationsteknik",
        "datateknik",
        "systemvetenskap",
        "informatik",
        "data",
        "mjukvara",
    },
    "data science": {
        "data science",
        "data analytics",
        "data analysis",
        "big data",
        "analytics",
        "analys",
    },
    "sustainability": {
        "sustainability",
        "sustainable",
        "hallbarhet",
        "hållbarhet",
        "green transition",
        "transition",
        "omstallning",
        "omställning",
    },
    "environmental science": {
        "miljo",
        "miljö",
        "environment",
        "environmental",
        "ecology",
        "ekologi",
        "climate",
        "klimat",
        "nature",
    },
    "engineering": {
        "engineering",
        "engineer",
        "ingenjor",
        "ingenjör",
        "technology",
        "teknik",
        "teknologi",
        "technical",
    },
    "business": {
        "business",
        "management",
        "leadership",
        "ekonomi",
        "economics",
        "organisation",
        "organization",
        "marketing",
        "finance",
    },
    "entrepreneurship": {
        "entrepreneurship",
        "startup",
        "founder",
        "innovation",
        "entreprenorskap",
        "entreprenörskap",
        "foretagande",
        "företagande",
    },
    "social sciences": {
        "social science",
        "social sciences",
        "society",
        "samhall",
        "samhälle",
        "policy",
        "politics",
        "politik",
    },
    "history": {
        "history",
        "historia",
        "archaeology",
        "arkeologi",
        "heritage",
    },
    "health sciences": {
        "health",
        "hälsa",
        "halsa",
        "medicine",
        "medicin",
        "public health",
        "nursing",
        "care",
        "healthcare",
    },
}

TOPIC_SYNONYMS = {
    "artificial intelligence": [
        "artificial intelligence",
        "machine learning",
        "ai",
        "maskininlärning",
        "computer science",
    ],
    "computer science": [
        "computer science",
        "software engineering",
        "programming",
        "datavetenskap",
        "artificial intelligence",
    ],
    "data science": [
        "data science",
        "analytics",
        "data analysis",
        "big data",
        "computer science",
    ],
    "sustainability": [
        "sustainability",
        "hållbarhet",
        "green transition",
        "environmental science",
        "climate",
    ],
    "environmental science": [
        "environmental science",
        "miljö",
        "climate",
        "ecology",
        "sustainability",
    ],
    "engineering": [
        "engineering",
        "technology",
        "ingenjör",
        "technical systems",
    ],
    "business": [
        "business",
        "economics",
        "management",
        "finance",
        "entrepreneurship",
    ],
    "entrepreneurship": [
        "entrepreneurship",
        "startup",
        "innovation",
        "business",
    ],
    "social sciences": [
        "social sciences",
        "policy",
        "society",
        "politics",
    ],
    "history": [
        "history",
        "heritage",
        "archaeology",
    ],
    "health sciences": [
        "health sciences",
        "health",
        "medicine",
        "public health",
    ],
}

TOKEN_RE = re.compile(r"[a-zA-ZåäöÅÄÖ0-9\-\+]+")


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _prepare_texts(texts: Iterable[str]) -> tuple[str, str]:
    raw = " ".join(str(text or "") for text in texts).lower()
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw, _fold(raw)


def infer_topics_from_text(*texts: str) -> List[str]:
    raw, folded = _prepare_texts(texts)
    if not raw:
        return []

    found: List[str] = []
    seen = set()

    for topic, aliases in TOPIC_ALIASES.items():
        alias_found = False
        for alias in aliases:
            pattern = rf"\b{re.escape(alias.lower())}\b"
            if re.search(pattern, raw) or re.search(rf"\b{re.escape(_fold(alias))}\b", folded):
                alias_found = True
                break
        if alias_found and topic not in seen:
            seen.add(topic)
            found.append(topic)

    for token in TOKEN_RE.findall(folded):
        if token.startswith("sustain") and "sustainability" not in seen:
            seen.add("sustainability")
            found.append("sustainability")
        if token.startswith("miljo") and "environmental science" not in seen:
            seen.add("environmental science")
            found.append("environmental science")
        if token.startswith("ingenj") and "engineering" not in seen:
            seen.add("engineering")
            found.append("engineering")
        if token.startswith("hist") and "history" not in seen:
            seen.add("history")
            found.append("history")

    return found


def normalize_interests(text: str) -> List[str]:
    return infer_topics_from_text(text)


def expand_interests_with_synonyms(interests: List[str]) -> List[str]:
    expanded: List[str] = []
    seen = set()

    for interest in interests:
        if not interest:
            continue
        canonical_candidates = infer_topics_from_text(interest) or [interest.strip().lower()]
        for canonical in canonical_candidates:
            for term in [canonical, *TOPIC_SYNONYMS.get(canonical, [])]:
                normalized = term.strip().lower()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                expanded.append(normalized)

    return expanded


def infer_primary_field(*texts: str) -> str:
    topics = infer_topics_from_text(*texts)
    return topics[0] if topics else "general"


def build_topic_bridge(topics: List[str]) -> str:
    bridge_terms = expand_interests_with_synonyms(topics)
    return ", ".join(bridge_terms)
