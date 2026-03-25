import re
from typing import Any, Dict, List, Optional

from app.services.language_normalization import normalize_interests
from app.services.metadata_normalization import (
    UNIVERSITY_ALIASES,
    normalize_city,
    normalize_language,
    normalize_study_pace,
    normalize_university,
)

KNOWN_CITIES = [
    "arvika",
    "bengtsfors",
    "boras",
    "borås",
    "gavle",
    "gävle",
    "stockholm",
    "gothenburg",
    "göteborg",
    "halmstad",
    "huddinge",
    "jonkoping",
    "jönköping",
    "kalmar",
    "karlskrona",
    "karlstad",
    "kristianstad",
    "lund",
    "uppsala",
    "malmo",
    "malmö",
    "linkoping",
    "linköping",
    "luleå",
    "norrkoping",
    "norrköping",
    "online",
    "distance",
    "piteå",
    "ronneby",
    "skellefteå",
    "skövde",
    "sundsvall",
    "trollhättan",
    "vasteras",
    "västerås",
    "västervik",
    "värnamo",
    "växjö",
    "örebro",
    "östersund",
    "umea",
    "umeå",
    "distans",
    "ortsoberoende",
]

KNOWN_COUNTRIES = [
    "sweden",
    "sverige",
    "norway",
    "denmark",
    "finland",
    "germany",
    "netherlands",
    "europe",
]

KNOWN_UNIVERSITIES = sorted(UNIVERSITY_ALIASES.keys(), key=len, reverse=True)

CAREER_PATTERNS = {
    "ai engineer": ["ai engineer", "ml engineer", "ai-utvecklare"],
    "software developer": ["software developer", "developer", "utvecklare"],
    "data scientist": ["data scientist", "data analyst", "dataanalytiker"],
    "researcher": ["researcher", "forskare", "research"],
    "entrepreneur": ["entrepreneur", "founder", "startup", "entreprenör"],
}


def _to_title(value: str) -> str:
    return normalize_city(value) or value.title()


class ProfileExtractor:
    @staticmethod
    def _normalize_list(values: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for value in values:
            clean = value.strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(clean)
        return out

    @staticmethod
    def _extract_locations(text: str, values: List[str]) -> List[str]:
        found: List[str] = []
        for item in values:
            if re.search(rf"\b{re.escape(item)}\b", text):
                found.append(_to_title(item))

        # Handle simple negations, e.g. "stockholm inte linköping".
        negated = set()
        for item in values:
            if re.search(rf"\b(?:inte|not|except)\s+{re.escape(item)}\b", text):
                negated.add(_to_title(item).lower())
        if negated:
            found = [city for city in found if city.lower() not in negated]

        return found

    @staticmethod
    def _extract_universities(text: str) -> Dict[str, List[str]]:
        preferred: List[str] = []
        excluded: List[str] = []

        for item in KNOWN_UNIVERSITIES:
            if not re.search(rf"\b{re.escape(item)}\b", text):
                continue

            normalized = normalize_university(item) or item.title()
            negated = any(
                re.search(pattern, text)
                for pattern in [
                    rf"\b(?:inte|ej|not|utan)\s+{re.escape(item)}\b",
                    rf"\bhar inte betygen för(?: att komma in på)?\s+{re.escape(item)}\b",
                    rf"\bkommer inte in på\s+{re.escape(item)}\b",
                ]
            )
            if negated:
                excluded.append(normalized)
            else:
                preferred.append(normalized)

        return {
            "preferred": ProfileExtractor._normalize_list(preferred),
            "excluded": ProfileExtractor._normalize_list(excluded),
        }

    @staticmethod
    def _extract_language(text: str) -> Optional[str]:
        if re.search(r"\b(engelska|english)\b", text):
            return normalize_language("english")
        if re.search(r"\b(svenska|swedish)\b", text):
            return normalize_language("swedish")
        return None

    @staticmethod
    def _extract_study_pace(text: str) -> Optional[str]:
        if re.search(r"\b(heltid|full[- ]?time|100 ?%)\b", text):
            return normalize_study_pace("full-time")
        if re.search(r"\b(deltid|part[- ]?time|25 ?%|50 ?%|75 ?%)\b", text):
            return normalize_study_pace("part-time")
        return None

    @staticmethod
    def _extract_study_level(text: str) -> Optional[str]:
        if re.search(r"\b(bachelor|kandidat|grundnivå|grundniva|undergraduate|bsc)\b", text):
            return "bachelor"
        if re.search(r"\b(master|magister|avancerad nivå|avancerad niva|graduate|msc)\b", text):
            return "master"
        if re.search(r"\b(phd|doctorate|doktorand|doctoral)\b", text):
            return "phd"
        return None

    @staticmethod
    def _extract_career_goals(text: str) -> List[str]:
        found: List[str] = []
        for goal, patterns in CAREER_PATTERNS.items():
            if any(re.search(rf"\b{re.escape(p)}\b", text) for p in patterns):
                found.append(goal)
        return found

    @classmethod
    def extract(cls, message: str) -> Dict[str, Any]:
        text = message.lower()
        university_matches = cls._extract_universities(text)
        return {
            "interests": cls._normalize_list(normalize_interests(message)),
            "preferred_cities": cls._normalize_list(
                cls._extract_locations(text, KNOWN_CITIES)
            ),
            "preferred_country": cls._normalize_list(
                cls._extract_locations(text, KNOWN_COUNTRIES)
            ),
            "language": cls._extract_language(text),
            "study_level": cls._extract_study_level(text),
            "study_pace": cls._extract_study_pace(text),
            "career_goals": cls._normalize_list(cls._extract_career_goals(text)),
            "preferred_universities": university_matches["preferred"],
            "excluded_universities": university_matches["excluded"],
        }
