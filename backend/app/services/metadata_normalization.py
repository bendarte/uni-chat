import re
import unicodedata
from typing import Optional


CITY_ALIASES = {
    "stockholm": "Stockholm",
    "solna": "Stockholm",
    "huddinge": "Stockholm",
    "kista": "Stockholm",
    "flemingsberg": "Stockholm",
    "sundbyberg": "Stockholm",
    "taby": "Stockholm",
    "täby": "Stockholm",
    "nacka": "Stockholm",
    "lidingo": "Stockholm",
    "lidingö": "Stockholm",
    "danderyd": "Stockholm",
    "sodertalje": "Stockholm",
    "södertälje": "Stockholm",
    "gothenburg": "Gothenburg",
    "goteborg": "Gothenburg",
    "göteborg": "Gothenburg",
    "malmo": "Malmo",
    "malmö": "Malmo",
    "uppsala": "Uppsala",
    "lund": "Lund",
    "linkoping": "Linkoping",
    "linköping": "Linkoping",
    "umea": "Umea",
    "umeå": "Umea",
    "jonkoping": "Jonkoping",
    "jönköping": "Jonkoping",
    "norrkoping": "Norrkoping",
    "norrköping": "Norrkoping",
    "vasteras": "Vasteras",
    "västerås": "Vasteras",
    "helsingborg": "Helsingborg",
    "boras": "Boras",
    "borås": "Boras",
    "karlstad": "Karlstad",
    "borlange": "Borlange",
    "borlänge": "Borlange",
    "gavle": "Gavle",
    "gävle": "Gavle",
    "halmstad": "Halmstad",
    "karlskrona": "Karlskrona",
    "sundsvall": "Sundsvall",
    "alnarp": "Alnarp",
    "lomma": "Lomma",
    "online": "Online",
    "distance": "Online",
    "distans": "Online",
    "ortsoberoende": "Online",
    "varied": "Multiple locations",
}

COUNTRY_ALIASES = {
    "sweden": "Sweden",
    "sverige": "Sweden",
    "denmark": "Denmark",
    "danmark": "Denmark",
    "norway": "Norway",
    "norge": "Norway",
    "finland": "Finland",
    "germany": "Germany",
    "tyskland": "Germany",
    "netherlands": "Netherlands",
    "nederlanderna": "Netherlands",
    "europe": "Europe",
    "europa": "Europe",
}

UNIVERSITY_ALIASES = {
    "stockholms universitet": "Stockholm University",
    "stockholm university": "Stockholm University",
    "su": "Stockholm University",
    "karolinska institutet": "Karolinska Institutet",
    "karolinska institute": "Karolinska Institutet",
    "kth royal institute of technology": "KTH Royal Institute of Technology",
    "kth": "KTH Royal Institute of Technology",
    "royal institute of technology": "KTH Royal Institute of Technology",
    "stockholm school of economics": "Stockholm School of Economics",
    "sse": "Stockholm School of Economics",
    "handelshögskolan": "Stockholm School of Economics",
    "handelshogskolan": "Stockholm School of Economics",
    "royal college of music in stockholm": "Royal College of Music in Stockholm",
    "university college of music education in stockholm": "University College of Music Education in Stockholm",
    "sophiahemmet högskola": "Sophiahemmet Högskola",
    "sophiahemmet hogskola": "Sophiahemmet Högskola",
}

FULL_TIME_MARKERS = {
    "100",
    "100%",
    "full-time",
    "full time",
    "heltid",
}
PART_TIME_MARKERS = {
    "25",
    "25%",
    "50",
    "50%",
    "75",
    "75%",
    "part-time",
    "part time",
    "deltid",
}


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def normalize_city(value: Optional[str]) -> Optional[str]:
    text = _clean(value)
    if not text:
        return None

    parts = [part.strip() for part in re.split(r"[\/,;]", text) if part.strip()]
    if len(parts) > 1:
        normalized_parts = [normalize_city(part) or part.title() for part in parts]
        return "/".join(normalized_parts)

    folded = _fold(text)
    canonical = CITY_ALIASES.get(folded)
    if canonical:
        return canonical

    if text.isupper():
        return text.title()
    return text


def city_filter_values(value: Optional[str]) -> list[str]:
    text = _clean(value)
    if not text:
        return []

    canonical = normalize_city(text) or text
    values = {text.lower(), canonical.lower()}
    for alias, mapped in CITY_ALIASES.items():
        if mapped.lower() == canonical.lower():
            values.add(alias.lower())
    return sorted(values)


def normalize_country(value: Optional[str]) -> Optional[str]:
    text = _clean(value)
    if not text:
        return None

    return COUNTRY_ALIASES.get(_fold(text), text.title())


def normalize_university(value: Optional[str]) -> Optional[str]:
    text = _clean(value)
    if not text:
        return None
    return UNIVERSITY_ALIASES.get(_fold(text), text)


def university_filter_values(value: Optional[str]) -> list[str]:
    text = _clean(value)
    if not text:
        return []

    canonical = normalize_university(text) or text
    values = {text.lower(), canonical.lower()}
    for alias, mapped in UNIVERSITY_ALIASES.items():
        if mapped.lower() == canonical.lower():
            values.add(alias.lower())
    return sorted(values)


def normalize_study_pace(value: Optional[str]) -> Optional[str]:
    text = _clean(value)
    if not text:
        return None

    lowered = text.lower()
    variants = {
        lowered,
        lowered.replace("_", "-"),
        lowered.replace("_", " "),
    }
    if any(any(marker in variant for variant in variants) for marker in FULL_TIME_MARKERS):
        return "full-time"
    if any(any(marker in variant for variant in variants) for marker in PART_TIME_MARKERS):
        return "part-time"

    percent_match = re.search(r"(\d{1,3})\s*%", lowered)
    if percent_match:
        return "full-time" if int(percent_match.group(1)) >= 100 else "part-time"

    return lowered


def normalize_language(value: Optional[str]) -> Optional[str]:
    text = _clean(value)
    if not text:
        return None

    lowered = text.lower()
    if lowered in {"english", "engelska"}:
        return "english"
    if lowered in {"swedish", "svenska"}:
        return "swedish"
    return lowered
