import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas import ChatResponse, Citation, RecommendationItem
from app.services.guidance_taxonomy import DOMAIN_FOLLOW_UP_QUESTIONS
from app.services.guidance_policy import GuidancePolicy
from app.services.intent_service import IntentService
from app.services.language_normalization import normalize_interests
from app.services.metadata_normalization import (
    normalize_city,
    normalize_language,
    normalize_study_pace,
    normalize_university,
)
from app.services.profile_extractor import ProfileExtractor
from app.services.recommendation_service import RecommendationService
from app.services.retrieval_service import RetrievalService
from app.services.session_service import SessionService

FOLLOW_UP_QUESTION_MAP = {
    "location": "Föredrar du att studera i Sverige eller är du öppen för hela Europa?",
    "study_level": "Letar du efter ett kandidat- eller masterprogram?",
    "language": "Föredrar du program på engelska eller svenska?",
    "interests": "Vilket ämne lockar mest — AI, ekonomi, teknik, hållbarhet eller något annat?",
    "career_goals": "Vilken typ av karriär siktar du på efter examen?",
}

FOLLOW_UP_QUESTION_MAP_EN = {
    "location": "Do you prefer to study in Sweden or are you open to all of Europe?",
    "study_level": "Are you looking for a bachelor's or master's programme?",
    "language": "Do you prefer programmes in English or Swedish?",
    "interests": "Which subject interests you most — AI, business, technology, sustainability or something else?",
    "career_goals": "What kind of career are you aiming for after graduation?",
}

_ENGLISH_FUNCTION_WORDS = {
    "the", "a", "an", "to", "of", "for", "is", "are", "was", "were",
    "will", "would", "want", "study", "in", "at", "i want", "i am",
    "can you", "what", "how", "where", "which", "do", "does", "my",
    "me", "we", "they", "have", "has", "had", "be", "been", "with",
    "not", "but", "and", "or", "if", "so", "that", "this", "it",
    "something", "anything", "sure", "maybe", "looking", "interested",
    "programme", "program", "degree", "university", "course",
}

_SWEDISH_SPECIFIC_WORDS = {
    "jag", "vill", "är", "och", "det", "ett", "på", "för", "med",
    "men", "om", "hur", "vad", "kan", "inte", "som", "till", "den",
    "de", "att", "en", "av", "sig", "vid", "eller", "dessa",
}


def detect_language(message: str) -> str:
    text = (message or "").lower()
    words = set(re.findall(r"[a-zA-ZåäöÅÄÖ]+", text))
    swedish_hits = words & _SWEDISH_SPECIFIC_WORDS
    if swedish_hits:
        return "sv"
    # Match English function words as whole words only (use word set for single-word phrases)
    single_word_en = {w for w in _ENGLISH_FUNCTION_WORDS if " " not in w}
    multi_word_en = {w for w in _ENGLISH_FUNCTION_WORDS if " " in w}
    english_hits = len(words & single_word_en) + sum(1 for phrase in multi_word_en if phrase in text)
    if english_hits >= 2:
        return "en"
    return "sv"


class ChatService:
    OPTION_STOPWORDS = {
        "och",
        "att",
        "med",
        "inom",
        "eller",
        "det",
        "den",
        "de",
        "jag",
        "vill",
        "låter",
        "bäst",
        "mest",
        "mer",
        "mindre",
        "for",
        "the",
        "and",
        "with",
        "than",
        "better",
    }

    def __init__(self) -> None:
        self.logger = logging.getLogger("uvicorn.error")
        self.sessions = SessionService()
        self.extractor = ProfileExtractor()
        self.retrieval = RetrievalService()
        self.recommender = RecommendationService()
        self.intent_service = IntentService()
        self.guidance_policy = GuidancePolicy()

    @staticmethod
    def _normalize_text(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return value.strip().lower()

    @staticmethod
    def _dedupe_list(values: List[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in values:
            clean = item.strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(clean)
        return out

    def _merge_filters_first(
        self,
        profile: Dict[str, Any],
        filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        merged = dict(profile)
        locked_fields = set(merged.get("locked_fields", []))
        filters = filters or {}

        if "level" in filters:
            level = self._normalize_text(filters.get("level"))
            if level:
                merged["study_level"] = level
                locked_fields.add("study_level")
            else:
                merged["study_level"] = None
                locked_fields.discard("study_level")

        if "language" in filters:
            language = self._normalize_text(filters.get("language"))
            if language:
                merged["language"] = normalize_language(language)
                locked_fields.add("language")
            else:
                merged["language"] = None
                locked_fields.discard("language")

        if "cities" in filters:
            cities = filters.get("cities") or []
            if cities:
                merged["preferred_cities"] = self._dedupe_list(
                    [normalize_city(str(city)) or str(city).title() for city in cities]
                )
                locked_fields.add("preferred_cities")
            else:
                merged["preferred_cities"] = []
                locked_fields.discard("preferred_cities")

        if "study_pace" in filters:
            study_pace = self._normalize_text(filters.get("study_pace"))
            if study_pace:
                merged["study_pace"] = normalize_study_pace(study_pace)
                locked_fields.add("study_pace")
            else:
                merged["study_pace"] = None
                locked_fields.discard("study_pace")

        if filters.get("field"):
            merged["interests"] = self._dedupe_list(
                [*merged.get("interests", []), str(filters["field"]).lower()]
            )

        merged["locked_fields"] = sorted(locked_fields)
        return merged

    def _merge_extracted_profile(
        self,
        profile: Dict[str, Any],
        extracted: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(profile)
        locked_fields = set(merged.get("locked_fields", []))

        merged["interests"] = self._dedupe_list(
            [*merged.get("interests", []), *extracted.get("interests", [])]
        )
        merged["career_goals"] = self._dedupe_list(
            [*merged.get("career_goals", []), *extracted.get("career_goals", [])]
        )
        merged["preferred_universities"] = self._dedupe_list(
            [*merged.get("preferred_universities", []), *extracted.get("preferred_universities", [])]
        )
        merged["excluded_universities"] = self._dedupe_list(
            [*merged.get("excluded_universities", []), *extracted.get("excluded_universities", [])]
        )
        merged["preferred_country"] = self._dedupe_list(
            [*merged.get("preferred_country", []), *extracted.get("preferred_country", [])]
        )

        if "preferred_cities" not in locked_fields:
            merged["preferred_cities"] = self._dedupe_list(
                [*merged.get("preferred_cities", []), *extracted.get("preferred_cities", [])]
            )

        if "language" not in locked_fields and not merged.get("language"):
            merged["language"] = extracted.get("language")

        if "study_level" not in locked_fields and not merged.get("study_level"):
            merged["study_level"] = extracted.get("study_level")

        if "study_pace" not in locked_fields and not merged.get("study_pace"):
            merged["study_pace"] = extracted.get("study_pace")

        merged["locked_fields"] = sorted(locked_fields)
        return merged

    @staticmethod
    def _looks_like_filter_override(message: str, extracted: Dict[str, Any]) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False

        has_extracted_filter = any(
            [
                extracted.get("preferred_cities"),
                extracted.get("preferred_universities"),
                extracted.get("excluded_universities"),
                extracted.get("language"),
                extracted.get("study_level"),
                extracted.get("study_pace"),
            ]
        )
        if not has_extracted_filter:
            return False

        if len(text.split()) <= 8:
            return True

        markers = [
            "inte ",
            "hellre ",
            "snarare ",
            "istället",
            "istallet",
            "och i ",
            "på distans",
            "distans",
            "online",
        ]
        return any(marker in text for marker in markers) or text.endswith("?")

    @staticmethod
    def _looks_like_place_follow_up(message: str, extracted: Dict[str, Any]) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False

        has_place_signal = bool(
            extracted.get("preferred_cities")
            or extracted.get("preferred_universities")
            or extracted.get("excluded_universities")
        )
        if not has_place_signal:
            return False

        if extracted.get("interests") or extracted.get("career_goals"):
            return False

        short_markers = [
            "och i ",
            "fler i ",
            "på ",
            "på su",
            "på kth",
            "på sse",
            "då",
        ]
        return len(text.split()) <= 8 or any(marker in text for marker in short_markers)

    @staticmethod
    def _has_explicit_university_constraint(
        extracted: Dict[str, Any],
        filters: Optional[Dict[str, Any]],
    ) -> bool:
        request_filters = filters or {}
        return bool(
            extracted.get("preferred_universities")
            or extracted.get("excluded_universities")
            or request_filters.get("universities")
            or request_filters.get("exclude_universities")
        )

    @staticmethod
    def _apply_direct_filter_overrides(
        profile: Dict[str, Any],
        extracted: Dict[str, Any],
        message: str,
    ) -> Dict[str, Any]:
        text = (message or "").strip().lower()
        updated = dict(profile)

        if extracted.get("preferred_cities"):
            updated["preferred_cities"] = extracted["preferred_cities"]
        elif any(token in text for token in ["på distans", "distans", "online", "ortsoberoende"]):
            updated["preferred_cities"] = ["Online"]

        if extracted.get("preferred_universities"):
            updated["preferred_universities"] = [
                normalize_university(value) or value
                for value in extracted["preferred_universities"]
            ]
        if extracted.get("excluded_universities"):
            updated["excluded_universities"] = ChatService._dedupe_list(
                [
                    *updated.get("excluded_universities", []),
                    *[
                        normalize_university(value) or value
                        for value in extracted["excluded_universities"]
                    ],
                ]
            )

        if extracted.get("study_level"):
            updated["study_level"] = extracted["study_level"]
        elif "inte master" in text:
            updated["study_level"] = None
        elif any(token in text for token in ["inte kandidat", "inte bachelor", "inte grundnivå", "inte grundniva"]):
            updated["study_level"] = None

        if extracted.get("language"):
            updated["language"] = extracted["language"]
        elif "inte engelska" in text or "inte english" in text:
            updated["language"] = None
        elif "inte svenska" in text or "inte swedish" in text:
            updated["language"] = None

        if extracted.get("study_pace"):
            updated["study_pace"] = extracted["study_pace"]

        return updated

    @staticmethod
    def _apply_direct_request_filter_overrides(
        filters: Optional[Dict[str, Any]],
        extracted: Dict[str, Any],
        message: str,
    ) -> Dict[str, Any]:
        text = (message or "").strip().lower()
        updated_filters = dict(filters or {})

        if extracted.get("preferred_cities"):
            updated_filters["cities"] = extracted["preferred_cities"]
        elif any(token in text for token in ["på distans", "distans", "online", "ortsoberoende"]):
            updated_filters["cities"] = ["Online"]

        if extracted.get("preferred_universities"):
            updated_filters["universities"] = extracted["preferred_universities"]
        if extracted.get("excluded_universities"):
            updated_filters["exclude_universities"] = extracted["excluded_universities"]

        if extracted.get("study_level"):
            updated_filters["level"] = extracted["study_level"]
        elif "inte master" in text or any(token in text for token in ["inte kandidat", "inte bachelor", "inte grundnivå", "inte grundniva"]):
            updated_filters["level"] = ""

        if extracted.get("language"):
            updated_filters["language"] = extracted["language"]
        elif "inte engelska" in text or "inte english" in text or "inte svenska" in text or "inte swedish" in text:
            updated_filters["language"] = ""

        if extracted.get("study_pace"):
            updated_filters["study_pace"] = extracted["study_pace"]

        return updated_filters

    # Suffixes that indicate the single word is a specific programme name rather than a vague topic.
    _PROGRAMME_SUFFIXES = (
        "programmet", "programme", "utbildningen", "utbildning",
        "kandidaten", "mastern", "examen",
    )

    @classmethod
    def _missing_fields(cls, profile: Dict[str, Any], message: str) -> List[str]:
        # Keep follow-up minimal: only ask when interests are truly missing.
        if profile.get("interests"):
            return []
        # Tracks or domain set → subject area already known, don't ask for interests.
        if profile.get("current_tracks") or profile.get("current_domain"):
            return []

        stripped = (message or "").strip().lower()
        words = stripped.split()
        # Single-word queries that look like programme names or academic subjects should search directly.
        _SUBJECT_SUFFIXES = ("vetenskap", "ekonomi", "teknik", "teknologi", "logi", "ologi", "nomik")
        if len(words) == 1 and (
            any(stripped.endswith(s) for s in cls._PROGRAMME_SUFFIXES)
            or any(stripped.endswith(s) for s in _SUBJECT_SUFFIXES)
        ):
            return []
        # Filter-only queries (level, pace, language, city, duration — no subject) should search directly.
        _FILTER_WORDS = frozenset({
            "master", "kandidat", "bachelor", "magister", "licentiat",
            "heltid", "deltid", "halvfart", "distans", "online",
            "deltidsstudier", "kvällsstudier", "kvälls",
            "engelska", "english", "svenska",
            "program", "programme", "programs", "programmes",
            "utbildning", "utbildningar",
            "flexibelt", "flexibel", "schema",
            "ettårig", "tvåårig", "treårig", "fyraårig", "femårig", "sexårig",
            "stockholm", "göteborg", "malmö", "lund", "uppsala", "linköping",
            "umeå", "örebro", "luleå", "karlstad",
        })
        _STOP_WORDS = frozenset({"på", "i", "och", "med", "för", "om"})
        _content_words = [w for w in words if w not in _STOP_WORDS]
        # Also treat duration adjectives (NNårig) as filter words via pattern.
        import re as _re
        if _content_words and all(w in _FILTER_WORDS or bool(_re.fullmatch(r'\d+årig', w)) for w in _content_words):
            return []
        if len(words) <= 2:
            return ["interests"]
        return []

    @staticmethod
    def _build_retrieval_query(message: str, profile: Dict[str, Any]) -> str:
        parts = [message]
        if profile.get("interests"):
            parts.append(" ".join(profile["interests"]))
        if profile.get("career_goals"):
            parts.append(" ".join(profile["career_goals"]))
        option = profile.get("selected_guidance_option") or {}
        if option.get("label"):
            parts.append(str(option["label"]))
        current_tracks = [
            str(track).replace("_", " ").strip()
            for track in (profile.get("current_tracks") or [])
            if str(track).strip()
        ]
        if current_tracks:
            parts.append(" ".join(current_tracks))
        if profile.get("study_level"):
            parts.append(str(profile["study_level"]))
        if profile.get("preferred_cities"):
            parts.append(" ".join(profile["preferred_cities"]))
        if profile.get("language"):
            parts.append(str(profile["language"]))
        if profile.get("study_pace"):
            parts.append(str(profile["study_pace"]))
        return " ".join(parts).strip()

    @classmethod
    def _build_scope_widen_query(cls, profile: Dict[str, Any]) -> str:
        base = "recommended study programs"
        return cls._build_retrieval_query(base, profile)

    @staticmethod
    def _build_effective_filters(profile: Dict[str, Any], request_filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        request_filters = dict(request_filters or {})
        cities = request_filters.get("cities") or profile.get("preferred_cities") or []
        locked = set(profile.get("locked_fields", []))
        city_locked = bool(request_filters.get("cities")) or ("preferred_cities" in locked and bool(cities))

        return {
            "cities": cities,
            "universities": request_filters.get("universities") or profile.get("preferred_universities") or [],
            "exclude_universities": request_filters.get("exclude_universities") or profile.get("excluded_universities") or [],
            "level": request_filters.get("level") or profile.get("study_level"),
            "language": request_filters.get("language") or profile.get("language"),
            "study_pace": request_filters.get("study_pace") or profile.get("study_pace"),
            "_city_locked": city_locked,
        }

    @staticmethod
    def _reset_domain_context(profile: Dict[str, Any]) -> Dict[str, Any]:
        reset = dict(profile)
        reset["interests"] = []
        reset["career_goals"] = []
        reset["current_tracks"] = []
        reset["current_domains"] = []
        reset["clarification_stage"] = None
        reset["clarification_options"] = []
        reset["selected_guidance_option"] = None
        return reset

    @staticmethod
    def _parse_option_choice(message: str, option_count: int) -> Optional[int]:
        text = (message or "").strip().lower()
        if not text or option_count <= 0:
            return None

        match = re.search(r"\b(?:nummer|nr|alternativ)?\s*([1-9])\b", text)
        if match:
            choice = int(match.group(1))
            if 1 <= choice <= option_count:
                return choice - 1

        ordinal_patterns = {
            0: [r"\bförsta\b", r"\bden första\b", r"\b1\b", r"\bett\b", r"\ben\b"],
            1: [r"\bandra\b", r"\bdet andra\b", r"\bden andra\b", r"\b2\b", r"\btvå\b"],
            2: [r"\btredje\b", r"\bden tredje\b", r"\b3\b", r"\btre\b"],
        }
        for index, patterns in ordinal_patterns.items():
            if index >= option_count:
                continue
            if any(re.search(pattern, text) for pattern in patterns):
                return index
        return None

    @classmethod
    def _tokenize_option_text(cls, value: str) -> List[str]:
        tokens = re.findall(r"[a-zA-ZåäöÅÄÖ\-]+", (value or "").lower())
        return [token for token in tokens if len(token) > 2 and token not in cls.OPTION_STOPWORDS]

    @classmethod
    def _match_option_by_text(cls, message: str, options: List[Dict[str, Any]]) -> Optional[int]:
        message_tokens = set(cls._tokenize_option_text(message))
        if not message_tokens:
            return None

        best_index = None
        best_score = 0
        for index, option in enumerate(options):
            label_tokens = set(cls._tokenize_option_text(str(option.get("label") or "")))
            question_tokens = set(cls._tokenize_option_text(str(option.get("question") or "")))
            next_question_tokens = set(
                cls._tokenize_option_text(" ".join(option.get("next_questions") or []))
            )
            score = (
                3 * len(message_tokens & label_tokens)
                + 2 * len(message_tokens & question_tokens)
                + 1 * len(message_tokens & next_question_tokens)
            )
            if score > best_score:
                best_score = score
                best_index = index

        if best_score >= 2:
            return best_index
        return None

    @staticmethod
    def _clear_guidance_state(profile: Dict[str, Any]) -> Dict[str, Any]:
        cleared = dict(profile)
        cleared["clarification_stage"] = None
        cleared["clarification_options"] = []
        cleared["selected_guidance_option"] = None
        cleared["current_question_type"] = None
        cleared["current_domain"] = None
        cleared["current_domains"] = []
        cleared["current_tracks"] = []
        return cleared

    @staticmethod
    def _selected_option_domains(profile: Dict[str, Any]) -> List[str]:
        option = profile.get("selected_guidance_option") or {}
        return [str(domain).strip().lower() for domain in option.get("domains", []) if str(domain).strip()]

    @staticmethod
    def _citation_snippet(program: Dict[str, Any]) -> str:
        text = str(program.get("description") or program.get("career_paths") or "").strip()
        if not text:
            return ""
        compact = " ".join(text.split())
        if len(compact) <= 280:
            return compact
        return compact[:277].rstrip() + "..."

    def _build_citations(
        self,
        programs: List[Dict[str, Any]],
        recommendations: List[Any],
        limit: int = 5,
    ) -> List[Citation]:
        if not programs or not recommendations:
            return []

        program_map = {
            str(program.get("program_id") or ""): program
            for program in programs
            if str(program.get("program_id") or "")
        }
        citations: List[Citation] = []
        for rec in recommendations:
            program = program_map.get(str(getattr(rec, "program_id", "") or ""))
            if not program:
                continue
            url = str(program.get("source_url") or "").strip()
            snippet = self._citation_snippet(program)
            if not url or not snippet:
                continue
            citations.append(
                Citation(
                    program_id=str(rec.program_id),
                    title=str(program.get("name") or rec.program),
                    university=str(program.get("university") or rec.university),
                    url=url,
                    snippet=snippet,
                )
            )
            if len(citations) >= limit:
                break
        return citations

    @staticmethod
    def _display_city(city: Optional[str]) -> str:
        mapping = {
            "Boras": "Borås",
            "Gavle": "Gävle",
            "Gothenburg": "Göteborg",
            "Jonkoping": "Jönköping",
            "Linkoping": "Linköping",
            "Malmo": "Malmö",
            "Norrkoping": "Norrköping",
            "Online": "distans",
            "Umea": "Umeå",
            "Vasteras": "Västerås",
        }
        value = str(city or "").strip()
        return mapping.get(value, value)

    @staticmethod
    def _display_level(level: Optional[str]) -> str:
        value = str(level or "").strip().lower()
        if value == "master":
            return "master"
        if value == "bachelor":
            return "kandidat"
        if value == "phd":
            return "forskarutbildning"
        return value

    @staticmethod
    def _display_language(language: Optional[str]) -> str:
        value = str(language or "").strip().lower()
        if value == "english":
            return "engelska"
        if value == "swedish":
            return "svenska"
        return value

    @staticmethod
    def _display_study_pace(study_pace: Optional[str]) -> str:
        value = str(study_pace or "").strip().lower()
        if value == "full-time":
            return "heltid"
        if value == "part-time":
            return "deltid"
        return value

    @classmethod
    def _listing_filter_summary(cls, profile: Dict[str, Any]) -> str:
        parts: List[str] = []
        if profile.get("study_level"):
            parts.append(cls._display_level(profile.get("study_level")))
        if profile.get("language"):
            parts.append(cls._display_language(profile.get("language")))
        if profile.get("study_pace"):
            parts.append(cls._display_study_pace(profile.get("study_pace")))
        if not parts:
            return ""
        return ", ".join(parts)

    @classmethod
    def _scope_label(cls, profile: Dict[str, Any]) -> str:
        universities = [str(item).strip() for item in profile.get("preferred_universities", []) if str(item).strip()]
        cities = [str(item).strip() for item in profile.get("preferred_cities", []) if str(item).strip()]

        if universities and cities and cities[0] != "Online":
            return f"på {universities[0]} i {cls._display_city(cities[0])}"
        if universities:
            return f"på {universities[0]}"
        if cities:
            city_label = cls._display_city(cities[0])
            if city_label == "distans":
                return "på distans"
            return f"i {city_label}"
        return "i ditt valda område"

    @staticmethod
    def _has_strict_location_scope(profile: Dict[str, Any]) -> bool:
        return bool(
            profile.get("preferred_cities")
            or profile.get("preferred_universities")
        )

    @classmethod
    def _location_broadening_hint(cls, profile: Dict[str, Any]) -> str:
        if not cls._has_strict_location_scope(profile):
            return ""
        return " Om du vill kan jag bredda sökningen till fler städer eller hela Sverige."

    @staticmethod
    def _has_topic_context(profile: Dict[str, Any]) -> bool:
        return bool(
            profile.get("interests")
            or profile.get("career_goals")
            or profile.get("current_domain")
            or profile.get("current_domains")
            or profile.get("current_tracks")
            or (profile.get("selected_guidance_option") or {}).get("label")
        )

    @staticmethod
    def _focus_label(profile: Dict[str, Any]) -> str:
        option = profile.get("selected_guidance_option") or {}
        if option.get("label"):
            return str(option["label"])

        track_labels = {
            "business_analytics": "business analytics",
            "product_management": "produktledning i teknikbolag",
            "ai_data": "AI och data",
            "software": "mjukvaruutveckling",
            "patient_care": "patientnära vård",
            "rehabilitation": "rehabilitering",
            "finance": "ekonomi och finans",
            "management": "affär och management",
        }
        for track in profile.get("current_tracks", []) or []:
            label = track_labels.get(str(track).strip().lower())
            if label:
                return label

        domain_labels = {
            "tech": "teknik",
            "business": "ekonomi och business",
            "healthcare": "vård och hälsa",
            "art": "design, media och musik",
            "psychology_social": "psykologi och socialt arbete",
        }
        domain = str(profile.get("current_domain") or "").strip().lower()
        return domain_labels.get(domain, "")

    @staticmethod
    def _hard_reset_context(profile: Dict[str, Any]) -> Dict[str, Any]:
        reset = dict(profile)
        reset["interests"] = []
        reset["career_goals"] = []
        reset["preferred_cities"] = []
        reset["preferred_country"] = []
        reset["preferred_universities"] = []
        reset["excluded_universities"] = []
        reset["language"] = None
        reset["study_level"] = None
        reset["study_pace"] = None
        reset["current_domain"] = None
        reset["current_domains"] = []
        reset["current_tracks"] = []
        reset["clarification_stage"] = None
        reset["current_question_type"] = None
        reset["clarification_options"] = []
        reset["selected_guidance_option"] = None
        return reset

    @staticmethod
    def _contains_widen_scope_phrase(message: str) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False
        widen_patterns = [
            "hela sverige",
            "i sverige då",
            "i sverige da",
            "i hela sverige",
            "någon annanstans",
            "nagon annanstans",
            "annanstans",
            "ingen stad",
            "utan stad",
            "anywhere in sweden",
            "nationwide",
        ]
        return any(pattern in text for pattern in widen_patterns)

    @classmethod
    def _looks_like_widen_scope_request(cls, message: str, profile: Dict[str, Any]) -> bool:
        has_location_context = bool(
            profile.get("preferred_cities")
            or profile.get("preferred_universities")
            or profile.get("excluded_universities")
        )
        if not has_location_context:
            return False
        return cls._contains_widen_scope_phrase(message)

    @staticmethod
    def _clear_location_constraints(profile: Dict[str, Any]) -> Dict[str, Any]:
        cleared = dict(profile)
        cleared["preferred_cities"] = []
        cleared["preferred_universities"] = []
        locked_fields = {
            field
            for field in cleared.get("locked_fields", [])
            if field not in {"preferred_cities", "preferred_universities"}
        }
        cleared["locked_fields"] = sorted(locked_fields)
        return cleared

    @staticmethod
    def _is_reset_command(message: str) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False
        commands = {
            "börja om",
            "borja om",
            "reset",
            "rensa",
            "ny sökning",
            "ny sokning",
            "ny fråga",
            "ny fraga",
            "starta om",
        }
        return text in commands

    def _build_reset_response(
        self,
        profile: Dict[str, Any],
        conversation_id: Optional[str],
        lang: str = "sv",
    ) -> ChatResponse:
        reset_profile = self._hard_reset_context(profile)
        self.sessions.save_profile(conversation_id, reset_profile)

        city = ""
        if reset_profile.get("preferred_cities"):
            city_value = self._display_city(reset_profile["preferred_cities"][0])
            city = "på distans" if city_value == "distans" else f"i {city_value}"

        if lang == "en":
            parts: List[str] = ["Okay, let's start over."]
            filter_summary = self._listing_filter_summary(reset_profile)
            if city and filter_summary:
                parts.append(f"I'll keep the filters {city} and {filter_summary}.")
            elif city:
                parts.append(f"I'll keep the filter {city}.")
            elif filter_summary:
                parts.append(f"I'll keep the filters {filter_summary}.")
            parts.append("Describe what you're looking for and we'll start fresh.")
        else:
            parts = ["Okej, vi börjar om."]
            filter_summary = self._listing_filter_summary(reset_profile)
            if city and filter_summary:
                parts.append(f"Jag behåller filtren {city} och {filter_summary}.")
            elif city:
                parts.append(f"Jag behåller filtret {city}.")
            elif filter_summary:
                parts.append(f"Jag behåller filtren {filter_summary}.")
            parts.append("Beskriv gärna vad du letar efter nu, så börjar vi från ett rent bord.")
        return ChatResponse(
            answer=" ".join(parts),
            questions=[],
            recommendations=[],
            citations=[],
            active_filters={
                "city": reset_profile.get("preferred_cities", [""])[0] if reset_profile.get("preferred_cities") else "",
                "level": (reset_profile.get("study_level") or "").capitalize(),
                "language": (reset_profile.get("language") or "").capitalize(),
                "study_pace": (reset_profile.get("study_pace") or "").replace("-", " ").capitalize(),
            },
        )

    @staticmethod
    def _has_explicit_search_constraints(
        extracted: Dict[str, Any],
        filters: Optional[Dict[str, Any]],
        message: str,
    ) -> bool:
        text = (message or "").strip().lower()
        request_filters = filters or {}
        return bool(
            extracted.get("preferred_cities")
            or extracted.get("preferred_universities")
            or extracted.get("excluded_universities")
            or extracted.get("study_level")
            or extracted.get("language")
            or extracted.get("study_pace")
            or request_filters.get("cities")
            or request_filters.get("universities")
            or request_filters.get("exclude_universities")
            or request_filters.get("level")
            or request_filters.get("language")
            or request_filters.get("study_pace")
            or any(token in text for token in ["på distans", "distans", "online", "ortsoberoende"])
        )

    @classmethod
    def _should_hard_reset_context(
        cls,
        message: str,
        extracted: Dict[str, Any],
        filters: Optional[Dict[str, Any]],
        intent: Dict[str, Any],
    ) -> bool:
        if intent.get("is_listing_query"):
            return True
        if extracted.get("preferred_cities") == ["Online"]:
            return True
        has_constraints = cls._has_explicit_search_constraints(extracted, filters, message)
        if has_constraints and (extracted.get("interests") or extracted.get("career_goals")):
            return True
        if has_constraints and cls._has_explicit_university_constraint(extracted, filters):
            return True
        return False

    def _build_listing_recommendations(
        self,
        programs: List[Dict[str, Any]],
        city: str,
        profile: Dict[str, Any],
    ) -> List[RecommendationItem]:
        recommendations: List[RecommendationItem] = []
        city_label = self._display_city(city)
        for program in programs[:8]:
            explanation_payload = self.recommender.explainer.generate_program_explanation(
                user_profile=profile,
                program=program,
            )
            recommendations.append(
                RecommendationItem(
                    program_id=str(program.get("program_id") or ""),
                    source_id=f"ref-{str(program.get('program_id') or '')[:8]}",
                    program=str(program.get("name") or ""),
                    university=str(program.get("university") or ""),
                    city=self._display_city(str(program.get("city") or city_label)),
                    explanation=explanation_payload.get("explanation", []),
                    source=str(program.get("source_url") or ""),
                    score=1.0,
                )
            )
        return recommendations

    def _consume_guidance_choice(
        self,
        profile: Dict[str, Any],
        message: str,
        conversation_id: Optional[str],
        lang: str = "sv",
    ) -> Optional[ChatResponse]:
        options = profile.get("clarification_options") or []
        if not options:
            return None

        choice_index = self._parse_option_choice(message, len(options))
        if choice_index is None:
            choice_index = self._match_option_by_text(message, options)
        if choice_index is None:
            return None

        option = options[choice_index]
        next_questions = option.get("next_questions", [])[:2]
        updated = dict(profile)
        updated["selected_guidance_option"] = option
        updated["clarification_options"] = []
        updated["clarification_stage"] = "awaiting_detail"
        updated["current_question_type"] = "detail_follow_up"
        if option.get("domains"):
            updated["current_domain"] = option["domains"][0]
            updated["current_domains"] = option["domains"][:3]
        if option.get("tracks"):
            updated["current_tracks"] = option["tracks"][:3]

        self.sessions.save_profile(conversation_id, updated)
        label = option.get("label_en", option["label"]) if lang == "en" else option["label"]
        if lang == "en":
            answer = (
                f"Great, I'll focus on {label}. "
                "Now I have a better sense of your direction, but I still want to understand which daily role suits you best."
            )
        else:
            answer = (
                f"Bra, då fokuserar jag på {label}. "
                "Nu vet jag bättre vilken riktning du lutar åt, men jag vill fortfarande förstå vilken vardag och roll som passar dig bäst."
            )
        return ChatResponse(
            answer=answer,
            questions=self._humanize_questions(next_questions, lang=lang),
            recommendations=[],
            citations=[],
        )

    @staticmethod
    def _is_constraint_only_follow_up(extracted: Dict[str, Any]) -> bool:
        has_constraints = bool(
            extracted.get("preferred_cities")
            or extracted.get("preferred_universities")
            or extracted.get("study_level")
            or extracted.get("language")
            or extracted.get("study_pace")
        )
        return has_constraints and not extracted.get("interests") and not extracted.get("career_goals")

    @staticmethod
    def _question_matches_level(question: str) -> bool:
        lowered = question.lower()
        return any(token in lowered for token in ["kandidat", "master", "nivå", "yrkesexamen", "grundutbildning", "vidareutbildning"])

    @staticmethod
    def _question_matches_location(question: str) -> bool:
        lowered = question.lower()
        return any(token in lowered for token in ["stad", "skola", "plats", "sverige"])

    @staticmethod
    def _question_matches_language(question: str) -> bool:
        lowered = question.lower()
        return any(token in lowered for token in ["engelska", "svenska", "språk"])

    @staticmethod
    def _question_matches_study_pace(question: str) -> bool:
        lowered = question.lower()
        return any(token in lowered for token in ["heltid", "deltid", "studietakt"])

    @classmethod
    def _filter_questions_for_known_constraints(
        cls,
        questions: List[str],
        profile: Dict[str, Any],
    ) -> List[str]:
        filtered: List[str] = []
        has_level = bool(profile.get("study_level"))
        has_location = bool(profile.get("preferred_cities") or profile.get("preferred_universities"))
        has_language = bool(profile.get("language"))
        has_study_pace = bool(profile.get("study_pace"))

        for question in questions:
            if has_level and cls._question_matches_level(question):
                continue
            if has_location and cls._question_matches_location(question):
                continue
            if has_language and cls._question_matches_language(question):
                continue
            if has_study_pace and cls._question_matches_study_pace(question):
                continue
            filtered.append(question)

        return filtered

    @classmethod
    def _constraint_acknowledgement(cls, extracted: Dict[str, Any]) -> str:
        parts: List[str] = []
        cities = extracted.get("preferred_cities") or []
        universities = extracted.get("preferred_universities") or []

        if universities:
            parts.append(f"Då utgår jag från {universities[0]}.")
        elif cities:
            city_label = cls._display_city(cities[0])
            if city_label == "distans":
                parts.append("Då fokuserar jag på distansupplägg.")
            else:
                parts.append(f"Då utgår jag från {city_label}.")

        if extracted.get("study_level"):
            parts.append(f"Jag håller mig till {cls._display_level(extracted.get('study_level'))}nivå.")
        if extracted.get("language"):
            parts.append(f"Jag prioriterar {cls._display_language(extracted.get('language'))}.")
        if extracted.get("study_pace"):
            parts.append(f"Jag utgår från {cls._display_study_pace(extracted.get('study_pace'))}.")

        return " ".join(parts).strip()

    def _remaining_follow_up_questions(self, profile: Dict[str, Any]) -> List[str]:
        option = profile.get("selected_guidance_option") or {}
        base_questions = option.get("next_questions") or DOMAIN_FOLLOW_UP_QUESTIONS.get(
            str(profile.get("current_domain") or "").strip().lower(),
            DOMAIN_FOLLOW_UP_QUESTIONS["other"],
        )
        return self._filter_questions_for_known_constraints(list(base_questions), profile)[:2]

    def _build_domain_follow_up_response(
        self,
        profile: Dict[str, Any],
        extracted: Dict[str, Any],
        conversation_id: Optional[str],
    ) -> Optional[ChatResponse]:
        if not self._is_constraint_only_follow_up(extracted):
            return None
        # Tracks already set — constraint message should flow to retrieval, not ask more questions.
        if profile.get("current_tracks"):
            return None

        updated = self._merge_extracted_profile(profile, extracted)
        updated["clarification_stage"] = profile.get("clarification_stage") or "awaiting_domain_specific_choice"
        updated["current_question_type"] = profile.get("current_question_type") or "domain_follow_up"
        questions = self._remaining_follow_up_questions(updated)
        if not questions:
            return None

        self.sessions.save_profile(conversation_id, updated)
        focus = self._focus_label(updated)
        acknowledgement = self._constraint_acknowledgement(extracted)
        if focus:
            answer = (
                f"{acknowledgement} För att guida dig vidare inom {focus} behöver jag bara smalna av innehållet lite till."
            ).strip()
        else:
            answer = (
                f"{acknowledgement} Då kan jag fokusera bättre på rätt typ av utbildningsspår."
            ).strip()

        return ChatResponse(
            answer=answer,
            questions=self._humanize_questions(questions),
            recommendations=[],
            citations=[],
        )

    def _build_art_theory_practice_follow_up(
        self,
        profile: Dict[str, Any],
        message: str,
        conversation_id: Optional[str],
    ) -> Optional[ChatResponse]:
        text = (message or "").strip().lower()
        if not text:
            return None

        theoretical_patterns = {"teoretisk", "teori", "mer teoretisk"}
        practical_patterns = {"praktisk", "praktiskt", "mer praktisk", "hands-on"}
        if not any(pattern in text for pattern in theoretical_patterns | practical_patterns):
            return None

        if str(profile.get("current_domain") or "").strip().lower() != "art":
            return None

        is_theoretical = any(pattern in text for pattern in theoretical_patterns)
        option_label = "teoretiska design- och mediespår" if is_theoretical else "praktiska design- och mediespår"
        questions = [
            "Är det främst design, media och kommunikation eller kultur- och teorispår som lockar mest?",
            "Vill du att jag prioriterar kandidat eller master?",
            "Ska jag hålla mig till en viss stad, distans eller är platsen öppen?",
        ]
        if not is_theoretical:
            questions[0] = "Är det främst design, media/produktion eller musikskapande som lockar mest?"

        updated = dict(profile)
        updated["selected_guidance_option"] = {
            "label": option_label,
            "domains": ["art"],
            "tracks": ["design_media"],
            "next_questions": questions,
        }
        updated["clarification_stage"] = "awaiting_detail"
        updated["current_question_type"] = "detail_follow_up"
        self.sessions.save_profile(conversation_id, updated)

        answer = (
            "Bra, då håller jag mig till ett mer teoretiskt kreativt spår."
            if is_theoretical
            else "Bra, då håller jag mig till ett mer praktiskt kreativt spår."
        )
        answer += " Nästa steg är att smalna av vilket område inom design och media som passar dig bäst."
        return ChatResponse(
            answer=answer,
            questions=self._humanize_questions(self._filter_questions_for_known_constraints(questions, updated)[:2]),
            recommendations=[],
            citations=[],
        )

    def _consume_question_type_follow_up(
        self,
        profile: Dict[str, Any],
        message: str,
        extracted: Dict[str, Any],
        conversation_id: Optional[str],
    ) -> Tuple[Dict[str, Any], Optional[ChatResponse]]:
        question_type = str(profile.get("current_question_type") or "").strip().lower()
        if not question_type:
            return profile, None

        if question_type == "domain_follow_up":
            art_follow_up = self._build_art_theory_practice_follow_up(profile, message, conversation_id)
            if art_follow_up:
                return profile, art_follow_up

        if question_type in {"domain_follow_up", "detail_follow_up"}:
            constraint_follow_up = self._build_domain_follow_up_response(profile, extracted, conversation_id)
            if constraint_follow_up:
                updated = self._merge_extracted_profile(profile, extracted)
                updated["clarification_stage"] = profile.get("clarification_stage") or "awaiting_domain_specific_choice"
                updated["current_question_type"] = question_type
                return updated, constraint_follow_up

        return profile, None

    @staticmethod
    def _humanize_questions(questions: List[str], lang: str = "sv") -> List[str]:
        humanized: List[str] = []
        for question in questions:
            clean = str(question or "").strip()
            if not clean:
                continue
            if clean.endswith("?"):
                humanized.append(clean)
                continue
            if lang == "en":
                humanized.append(f"Does {clean} sound most interesting to you right now?")
            else:
                humanized.append(f"Låter {clean} mest intressant för dig just nu?")
        return humanized

    @staticmethod
    def _detail_follow_up(message: str, selected_option: Dict[str, Any]) -> Optional[ChatResponse]:
        text = (message or "").strip().lower()
        if not text:
            return None

        option_label = str(selected_option.get("label") or "det spåret")
        analysis_terms = {"analys", "data", "utredning", "research", "policy", "strategi"}
        design_terms = {"design", "visuellt", "kreativt", "creative", "form", "grafisk"}
        people_terms = {"människor", "people", "stöd", "hjälpa", "rådgivning", "patient"}
        tech_terms = {"teknik", "technical", "system", "utveckling", "digital", "plattform"}
        strategy_terms = {"strategi", "strategy", "affär", "business", "positionering", "ledning", "management"}
        broad_patterns = [
            "bred utbildning",
            "brett program",
            "bredare utbildning",
            "broad education",
            "broad programme",
            "broad program",
        ]
        specialized_patterns = [
            "specialiserat",
            "specialiserad",
            "specialiserat spår",
            "specialized",
            "specialised",
            "nischat",
        ]
        low_people_patterns = [
            "inte så mycket människor",
            "inte människor",
            "mindre människor",
            "less people",
            "not so much people",
        ]
        low_creative_patterns = [
            "inte så kreativt",
            "mindre kreativt",
            "less creative",
            "inte design",
        ]
        business_over_tech_patterns = [
            "mer affär än teknik",
            "more business than tech",
            "mer affär än tekniskt",
        ]
        analysis_over_people_patterns = [
            "hellre analys än människor",
            "more analysis than people",
            "mer analys än människor",
            "analys snarare än människor",
        ]
        strategy_over_creativity_patterns = [
            "mer strategi än kreativitet",
            "more strategy than creativity",
            "strategi snarare än kreativitet",
        ]
        theoretical_patterns = [
            "teoretisk",
            "mer teoretisk",
            "teori",
            "theoretical",
        ]
        practical_patterns = [
            "praktisk",
            "mer praktisk",
            "praktiskt",
            "hands-on",
            "practical",
        ]

        tokens = set(re.findall(r"[a-zA-ZåäöÅÄÖ\-]+", text))
        if any(pattern in text for pattern in theoretical_patterns):
            return ChatResponse(
                answer=(
                    f"Bra, då verkar du luta åt en mer teoretisk väg inom {option_label}. "
                    "Då bör vi prioritera utbildningar där analys, koncept och förståelse väger tyngre än ren produktion."
                ),
                questions=[
                    "Är det främst design, kommunikation/media eller ett mer analytiskt kulturspår som lockar?",
                    "Vill du att jag håller mig till kandidatnivå eller är även master relevant?",
                ],
                recommendations=[],
                citations=[],
            )
        if any(pattern in text for pattern in practical_patterns):
            return ChatResponse(
                answer=(
                    f"Bra, då verkar du vilja ha ett mer praktiskt spår inom {option_label}. "
                    "Det pekar mer mot utbildningar där skapande, produktion eller konkret tillämpning är centrala."
                ),
                questions=[
                    "Är det främst design, media/produktion eller musikskapande som lockar mest?",
                    "Ska jag prioritera program där du får arbeta mer hands-on än teoretiskt?",
                ],
                recommendations=[],
                citations=[],
            )
        if any(pattern in text for pattern in analysis_over_people_patterns):
            return ChatResponse(
                answer=(
                    f"Bra, då verkar du föredra ett mer analytiskt och mindre människonära spår inom {option_label}. "
                    "Det hjälper, eftersom den skillnaden brukar avgöra om vi ska tänka mer data, strategi eller verksamhetsanalys."
                ),
                questions=[
                    "Vill du gå mer mot data och analys, utredning och policy eller affärs- och verksamhetsutveckling?",
                    "Ska jag prioritera utbildningar som leder till analytiska roller bakom kulisserna snarare än direkt människonära arbete?",
                ],
                recommendations=[],
                citations=[],
            )
        if any(pattern in text for pattern in business_over_tech_patterns):
            return ChatResponse(
                answer=(
                    f"Bra, då verkar affären väga tyngre än tekniken inom {option_label}. "
                    "Det pekar mer mot strategi, marknad och verksamhetsutveckling än mot rena teknikroller."
                ),
                questions=[
                    "Lockar marknad, affärsutveckling eller kommunikation mest?",
                    "Vill du att jag drar dig bort från utbildningar som är för tekniktunga?",
                ],
                recommendations=[],
                citations=[],
            )
        if any(pattern in text for pattern in strategy_over_creativity_patterns):
            return ChatResponse(
                answer=(
                    f"Bra, då lutar du mer åt strategi än kreativ produktion inom {option_label}. "
                    "Då bör vi titta på spår som leder mot analys, positionering eller affärsnära roller."
                ),
                questions=[
                    "Är affär, kommunikation eller verksamhetsutveckling mest intressant för dig?",
                    "Vill du att jag prioriterar program med mer analys och mindre ren produktion eller design?",
                ],
                recommendations=[],
                citations=[],
            )
        if any(pattern in text for pattern in low_people_patterns):
            return ChatResponse(
                answer=(
                    f"Bra, då verkar du inte vilja ha ett lika människonära spår inom {option_label}. "
                    "Det pekar mer mot analys, strategi eller teknik än mot roller med mycket direktkontakt."
                ),
                questions=[
                    "Vill du hellre arbeta med analys och utredning, strategi och planering eller tekniska/digitala verktyg?",
                    "Ska jag prioritera utbildningar som leder till mer analytiska och mindre människonära roller?",
                ],
                recommendations=[],
                citations=[],
            )
        if any(pattern in text for pattern in low_creative_patterns):
            return ChatResponse(
                answer=(
                    f"Bra, då verkar du vilja tona ner det mest kreativa inom {option_label}. "
                    "Då bör vi snarare leta efter utbildningar med mer analys, strategi eller affärsinnehåll."
                ),
                questions=[
                    "Vill du gå mer mot analys, strategi eller affär/kommunikation?",
                    "Är det viktigare att utbildningen känns trygg på arbetsmarknaden än att den är starkt kreativ?",
                ],
                recommendations=[],
                citations=[],
            )
        if any(pattern in text for pattern in broad_patterns):
            return ChatResponse(
                answer=(
                    f"Bra, då verkar du föredra en bredare utbildning inom {option_label} snarare än ett smalt specialistspår. "
                    "Det hjälper, eftersom jag då bör prioritera program som håller fler dörrar öppna tidigt."
                ),
                questions=[
                    "Vill du att den breda utbildningen lutar mer åt ekonomi och analys eller mer åt affär, management och organisation?",
                    "Är det viktigare att få en stabil grund först än att nischa dig redan från början?",
                ],
                recommendations=[],
                citations=[],
            )
        if any(pattern in text for pattern in specialized_patterns):
            return ChatResponse(
                answer=(
                    f"Bra, då verkar du vilja gå mot ett mer specialiserat spår inom {option_label}. "
                    "Då kan jag prioritera utbildningar som är tydligare nischade från början."
                ),
                questions=[
                    "Vill du nischa dig mer mot analys och ekonomi, affär och management eller tillämpade områden som entreprenörskap och marknad?",
                    "Är du ute efter ett program som tydligare formar en viss yrkesprofil redan under utbildningen?",
                ],
                recommendations=[],
                citations=[],
            )
        if "mer strategi än kreativitet" in text or ("strategi" in tokens and "kreativitet" in tokens):
            return ChatResponse(
                answer=(
                    f"Bra, då lutar du mer åt ett strategiskt än ett kreativt spår inom {option_label}. "
                    "Det gör att vi bör prioritera roller där analys, positionering eller verksamhetsutveckling är viktigare än skapande."
                ),
                questions=[
                    "Lockar strategi, affär eller kommunikation mest?",
                    "Vill du att jag drar dig bort från de mest design- och skapandeinriktade programmen?",
                ],
                recommendations=[],
                citations=[],
            )
        if "mer tekn" in text or "mer digital" in text or "det där men mer tekniskt" in text:
            return ChatResponse(
                answer=(
                    f"Bra, då verkar du vilja ha en mer teknisk version av {option_label}. "
                    "Då bör vi prioritera program där system, digitala verktyg eller produktutveckling spelar större roll."
                ),
                questions=[
                    "Vill du att tekniken ska handla mer om system och utveckling eller mer om hur människor använder digitala verktyg?",
                    "Ska jag prioritera program med tydligare teknisk tyngd än kreativ eller verksamhetsnära profil?",
                ],
                recommendations=[],
                citations=[],
            )
        if tokens & analysis_terms:
            return ChatResponse(
                answer=(
                    f"Bra, då lutar du åt ett mer analytiskt spår inom {option_label}. "
                    "Det hjälper, för det pekar mot andra typer av utbildningar än mer kreativa eller praktiska roller."
                ),
                questions=[
                    "Vill du arbeta mer med data och analys, utredning och policy eller strategiska beslut?",
                    "Är det viktigare att utbildningen är samhälls- och verksamhetsnära eller mer teknisk?",
                ],
                recommendations=[],
                citations=[],
            )
        if tokens & design_terms:
            return ChatResponse(
                answer=(
                    f"Bra, då lutar du åt en mer design- eller skapande inriktning inom {option_label}. "
                    "Det gör stor skillnad för vilka program som faktiskt blir relevanta."
                ),
                questions=[
                    "Vill du arbeta mer med visuell form, användarupplevelse eller innehåll och berättande?",
                    "Vill du att jag prioriterar program som är mer kreativa än tekniska?",
                ],
                recommendations=[],
                citations=[],
            )
        if tokens & people_terms:
            return ChatResponse(
                answer=(
                    f"Bra, då verkar människonärheten vara viktig inom {option_label}. "
                    "Då bör vi hålla oss borta från spår som mest leder till analys bakom kulisserna."
                ),
                questions=[
                    "Vill du arbeta direkt med människor i vardagen eller mer med stödjande planering och rådgivning?",
                    "Föredrar du ett yrke med tydlig praktisk vardag eller ett mer strategiskt och samtalsbaserat arbete?",
                ],
                recommendations=[],
                citations=[],
            )
        if tokens & tech_terms:
            return ChatResponse(
                answer=(
                    f"Bra, då verkar teknikinnehållet vara viktigt inom {option_label}. "
                    "Det talar för att vi ska prioritera program där digitala verktyg, system eller produktarbete är centrala."
                ),
                questions=[
                    "Vill du arbeta mer med system och teknik, eller med hur människor använder tekniken?",
                    "Ska jag prioritera program med tydligare teknisk tyngd än verksamhets- eller designfokus?",
                ],
                recommendations=[],
                citations=[],
            )
        if tokens & strategy_terms:
            return ChatResponse(
                answer=(
                    f"Bra, då verkar det strategiska innehållet vara viktigare för dig inom {option_label}. "
                    "Det brukar peka mot utbildningar som leder till planering, positionering eller affärsnära roller snarare än ren produktion."
                ),
                questions=[
                    "Vill du arbeta mer med affär, kommunikation eller verksamhetsutveckling?",
                    "Ska jag prioritera utbildningar med mer strategi än kreativ produktion eller praktiskt genomförande?",
                ],
                recommendations=[],
                citations=[],
            )
        return None

    def handle_message(
        self,
        message: str,
        filters: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
    ) -> ChatResponse:
        lang = detect_language(message)
        # 1) load profile from Redis
        profile = self.sessions.load_profile(conversation_id)
        profile = self._merge_filters_first(profile, filters)
        widen_scope_requested = self._looks_like_widen_scope_request(message, profile)
        if self._is_reset_command(message):
            return self._build_reset_response(profile, conversation_id, lang)
        guidance_choice_response = self._consume_guidance_choice(profile, message, conversation_id, lang=lang)
        if guidance_choice_response:
            return guidance_choice_response

        normalized_interests = normalize_interests(message)
        extracted = self.extractor.extract(message)
        extracted["interests"] = self._dedupe_list(
            [*normalized_interests, *extracted.get("interests", [])]
        )
        if (
            self._contains_widen_scope_phrase(message)
            and not self._has_topic_context(profile)
            and not extracted.get("interests")
            and not extracted.get("career_goals")
        ):
            if lang == "en":
                return ChatResponse(
                    answer="I can broaden the location, but I first need to know which subject or programme track you want to broaden the search for.",
                    questions=[
                        "Which area do you have in mind, for example AI and data, business, healthcare or sustainability?"
                    ],
                    recommendations=[],
                    citations=[],
                )
            return ChatResponse(
                answer="Jag kan bredda platsen, men jag behöver först veta vilket ämne eller programspår du vill bredda sökningen för.",
                questions=[
                    "Vilket område tänker du på, till exempel AI och data, business, vård eller hållbarhet?"
                ],
                recommendations=[],
                citations=[],
            )

        if widen_scope_requested:
            profile = self._clear_location_constraints(profile)

        profile, typed_follow_up_response = self._consume_question_type_follow_up(
            profile,
            message,
            extracted,
            conversation_id,
        )
        if typed_follow_up_response:
            return typed_follow_up_response

        reset_probe_intent = self.intent_service.analyze(message, profile={})
        if self._should_hard_reset_context(message, extracted, filters, reset_probe_intent):
            profile = self._hard_reset_context(profile)

        intent = self.intent_service.analyze(message, profile=profile)

        if widen_scope_requested:
            if profile.get("current_domain") and not intent.get("domain"):
                intent["domain"] = profile.get("current_domain")
            if profile.get("current_domains") and not intent.get("domains"):
                intent["domains"] = profile.get("current_domains", [])
            if profile.get("current_tracks") and not intent.get("career_track_candidates"):
                intent["career_track_candidates"] = profile.get("current_tracks", [])
            intent["is_vague"] = False
            intent["is_exploratory"] = False
            intent["needs_clarification"] = False

        # If the profile already has tracks set and the message is a constraint-only follow-up,
        # override is_vague/is_exploratory so we proceed to retrieval instead of asking again.
        if profile.get("current_tracks") and not intent.get("career_track_candidates"):
            intent["career_track_candidates"] = profile.get("current_tracks", [])
            intent["is_vague"] = False
            intent["is_exploratory"] = False

        # If the user provided explicit sidebar filters (city, level, language) they have already
        # narrowed down the search — do not trigger clarification regardless of vaguer wording.
        if filters and any(filters.get(k) for k in ("level", "cities", "language", "study_pace")):
            intent["is_vague"] = False
            intent["is_exploratory"] = False
            intent["needs_clarification"] = False

        # Programme names, academic subjects, and short queries with a detected domain should search directly.
        _stripped = message.strip().lower()
        _words = _stripped.split()
        _ACADEMIC_SUFFIXES = ("vetenskap", "ekonomi", "teknik", "teknologi", "logi", "ologi", "nomik", "kunskap")
        if (
            (len(_words) == 1 and (
                any(_stripped.endswith(s) for s in self._PROGRAMME_SUFFIXES)
                or any(_stripped.endswith(s) for s in _ACADEMIC_SUFFIXES)
            ))
            # If domain is detected and query is short, search directly — even if phrasing is exploratory.
            or (len(_words) <= 6 and intent.get("domain") and not intent.get("is_comparison_query"))
        ):
            intent["is_vague"] = False
            intent["is_exploratory"] = False
            intent["needs_clarification"] = False

        # "X och Y" compound topic queries where a domain is already detected should search directly.
        if (
            " och " in _stripped
            and len(_words) <= 9
            and intent.get("domain")
            and not intent.get("is_comparison_query")
        ):
            intent["is_vague"] = False
            intent["is_exploratory"] = False

        # "master/kandidat i X" — study level stated explicitly in text means the query is not vague.
        _LEVEL_WORDS = ("master", "kandidat", "bachelor", "magister", "licentiat")
        if (
            len(_words) <= 5
            and any(w in _LEVEL_WORDS for w in _words)
            and intent.get("domain")
        ):
            intent["is_vague"] = False
            intent["is_exploratory"] = False

        # Filter-only queries (level, pace, language, city, duration with no subject) should search directly.
        _FILTER_WORDS_INTENT = frozenset({
            "master", "kandidat", "bachelor", "magister", "licentiat",
            "heltid", "deltid", "halvfart", "distans", "online",
            "deltidsstudier", "kvällsstudier", "kvälls",
            "engelska", "english", "svenska",
            "program", "programme", "programs", "programmes",
            "utbildning", "utbildningar",
            "flexibelt", "flexibel", "schema",
            "ettårig", "tvåårig", "treårig", "fyraårig", "femårig", "sexårig",
            "stockholm", "göteborg", "malmö", "lund", "uppsala", "linköping",
            "umeå", "örebro", "luleå", "karlstad",
        })
        _STOP_WORDS_INTENT = frozenset({"på", "i", "och", "med", "för", "om"})
        _content_intent = [w for w in _words if w not in _STOP_WORDS_INTENT]
        import re as _re_intent
        if _content_intent and all(w in _FILTER_WORDS_INTENT or bool(_re_intent.fullmatch(r'\d+årig', w)) for w in _content_intent):
            intent["is_vague"] = False
            intent["is_exploratory"] = False
            intent["needs_clarification"] = False

        previous_domains = set(profile.get("current_domains") or ([profile["current_domain"]] if profile.get("current_domain") else []))
        current_domains = set(intent.get("domains") or ([intent["domain"]] if intent.get("domain") else []))
        if current_domains and previous_domains and not (previous_domains & current_domains):
            profile = self._reset_domain_context(profile)
        elif profile.get("clarification_stage") == "awaiting_detail" and (
            intent.get("needs_clarification") or (current_domains and not (previous_domains & current_domains))
        ):
            profile = self._clear_guidance_state(profile)
        elif profile.get("clarification_stage") == "awaiting_detail" and profile.get("selected_guidance_option"):
            selected_domains = self._selected_option_domains(profile)
            if selected_domains and not intent.get("domains"):
                intent["domain"] = selected_domains[0]
                intent["domains"] = selected_domains
            if profile.get("current_tracks") and not intent.get("career_track_candidates"):
                intent["career_track_candidates"] = profile.get("current_tracks", [])
            intent["is_vague"] = False
            intent["is_exploratory"] = False
            intent["needs_clarification"] = False
            preference_follow_up = self._detail_follow_up(message, profile.get("selected_guidance_option") or {})
            if preference_follow_up:
                return preference_follow_up

        # 2) frontend filters override first
        profile = self._merge_filters_first(profile, filters)

        if self._looks_like_filter_override(message, extracted):
            profile = self._apply_direct_filter_overrides(profile, extracted, message)
            filters = self._apply_direct_request_filter_overrides(filters, extracted, message)

        if widen_scope_requested:
            profile = self._clear_location_constraints(profile)
            widened_filters = dict(filters or {})
            widened_filters["cities"] = []
            widened_filters["universities"] = []
            filters = widened_filters

        force_distance_listing = extracted.get("preferred_cities") == ["Online"] and not extracted.get("interests") and not extracted.get("career_goals")

        if force_distance_listing:
            intent["is_listing_query"] = True

        if (
            intent.get("is_listing_query")
            and not extracted.get("interests")
            and not extracted.get("career_goals")
        ):
            intent["domain"] = None
            intent["domains"] = []
            intent["career_track_candidates"] = []
            intent["is_vague"] = False
            intent["is_exploratory"] = False
            profile = self._hard_reset_context(profile)
            profile = self._merge_filters_first(profile, filters)

        if self._looks_like_place_follow_up(message, extracted):
            if profile.get("current_domain") and not intent.get("domain"):
                intent["domain"] = profile.get("current_domain")
            if profile.get("current_domains") and not intent.get("domains"):
                intent["domains"] = profile.get("current_domains", [])
            if profile.get("current_tracks") and not intent.get("career_track_candidates"):
                intent["career_track_candidates"] = profile.get("current_tracks", [])
            intent["is_vague"] = False
            intent["is_exploratory"] = False

        if self._has_explicit_university_constraint(extracted, filters):
            if profile.get("current_domain") and not intent.get("domain"):
                intent["domain"] = profile.get("current_domain")
            if profile.get("current_domains") and not intent.get("domains"):
                intent["domains"] = profile.get("current_domains", [])
            if profile.get("current_tracks") and not intent.get("career_track_candidates"):
                intent["career_track_candidates"] = profile.get("current_tracks", [])
            intent["is_vague"] = False
            intent["is_exploratory"] = False
            intent["needs_clarification"] = False

        if extracted.get("preferred_cities") == ["Online"]:
            profile["current_domain"] = None
            profile["current_domains"] = []
            profile["current_tracks"] = []

        # 4) merge extracted data without overwriting locked fields
        profile = self._merge_extracted_profile(profile, extracted)
        if intent.get("domain"):
            profile["current_domain"] = intent["domain"]
        if intent.get("domains"):
            profile["current_domains"] = intent["domains"][:3]
        if intent.get("career_track_candidates"):
            profile["current_tracks"] = intent["career_track_candidates"]
        elif intent.get("domain"):
            profile["current_tracks"] = []

        # When the user mentions a specific role ("läkare", "sjuksköterska" etc.), add it to
        # career_goals so that the explanation service can reference it explicitly.
        if intent.get("matched_role_terms") and not profile.get("career_goals"):
            profile["career_goals"] = self._dedupe_list(intent["matched_role_terms"])

        # persist session after every message
        self.sessions.save_profile(conversation_id, profile)

        # 5) advisor clarification mode for vague domain-level goals
        if self.guidance_policy.should_clarify(intent):
            answer = self.guidance_policy.build_clarification_answer(intent, lang=lang)
            profile["clarification_stage"] = "awaiting_domain_specific_choice"
            if intent.get("clarification_options") and not intent.get("domain"):
                profile["current_question_type"] = "top_level_domain"
            elif intent.get("clarification_options") or intent.get("bridge_path_suggestions"):
                profile["current_question_type"] = "option_choice"
            else:
                profile["current_question_type"] = "domain_follow_up"
            profile["clarification_options"] = (
                intent.get("clarification_options")
                or intent.get("bridge_path_suggestions")
                or []
            )
            self.sessions.save_profile(conversation_id, profile)
            fup_key = "follow_up_questions_en" if lang == "en" else "follow_up_questions"
            return ChatResponse(
                answer=answer,
                questions=self._humanize_questions(intent.get(fup_key, intent.get("follow_up_questions", []))[:3], lang=lang),
                recommendations=[],
                citations=[],
                active_filters={
                    "city": profile.get("preferred_cities")[0] if profile.get("preferred_cities") else "",
                    "level": (profile.get("study_level") or "").capitalize(),
                    "language": (profile.get("language") or "").capitalize(),
                    "study_pace": (profile.get("study_pace") or "").replace("-", " ").capitalize(),
                },
            )

        # 6) follow-up questions only if strictly needed
        missing = self._missing_fields(profile, message)
        fup_map = FOLLOW_UP_QUESTION_MAP_EN if lang == "en" else FOLLOW_UP_QUESTION_MAP
        questions = [fup_map[m] for m in missing if m in fup_map][:2]
        if questions:
            answer = (
                "I need a bit more information before I can recommend programmes."
                if lang == "en"
                else "Jag behöver lite mer information innan jag kan rekommendera program."
            )
            return ChatResponse(answer=answer, questions=self._humanize_questions(questions, lang=lang), recommendations=[], citations=[])

        # 7) log final merged profile before retrieval
        self.logger.info("Final merged profile before retrieval: %s", profile)

        retrieval_query = self._build_retrieval_query(
            message.strip() or "study program recommendations",
            profile,
        )
        if widen_scope_requested and not extracted.get("interests") and not extracted.get("career_goals"):
            retrieval_query = self._build_scope_widen_query(profile)
        effective_filters = self._build_effective_filters(profile, filters)
        effective_filters.update(self.guidance_policy.build_retrieval_filters(intent))
        if intent.get("is_listing_query"):
            programs = self.retrieval.list_programs(filters=effective_filters, limit=8)
            citation_programs = programs
            listing_city = profile.get("preferred_cities")[0] if profile.get("preferred_cities") else (
                "the selected city" if lang == "en" else "den valda staden"
            )
            recommendations = self._build_listing_recommendations(programs, listing_city, profile)
        else:
            programs = self.retrieval.search_programs(
                query=retrieval_query,
                filters=effective_filters,
                profile=profile,
            )
            citation_programs = programs
            recommendations = self.recommender.generate(profile, programs, limit=5)

        # Defensive fallback: still avoid an empty response body.
        widened_from_city: Optional[str] = None
        if not recommendations and not intent.get("is_listing_query"):
            fallback_query = self._build_retrieval_query("recommended study programs", profile)
            fallback_programs = self.retrieval.search_programs(
                query=fallback_query,
                filters=effective_filters,
                profile=profile,
            )
            citation_programs = fallback_programs
            recommendations = self.recommender.generate(profile, fallback_programs, limit=5)

        # If city filter is active and results are still empty, widen to all of Sweden.
        # Distance/Online listing queries are also allowed to widen since the DB has very few distance programmes.
        _is_distance_listing = (effective_filters.get("cities") or []) == ["Online"]
        if not recommendations and (not intent.get("is_listing_query") or _is_distance_listing) and effective_filters.get("cities"):
            original_cities = effective_filters.get("cities") or []
            widened_profile = dict(profile)
            widened_profile["preferred_cities"] = []
            widened_filters = dict(effective_filters)
            widened_filters["cities"] = []
            widened_filters["_city_locked"] = False
            widened_programs = self.retrieval.search_programs(
                query=retrieval_query,
                filters=widened_filters,
                profile=widened_profile,
            )
            widened_recs = self.recommender.generate(widened_profile, widened_programs, limit=5)
            if widened_recs:
                recommendations = widened_recs
                citation_programs = widened_programs
                widened_from_city = self._display_city(original_cities[0]) if original_cities else (
                    "your selected city" if lang == "en" else "din valda stad"
                )

        # If level filter is active and results are still empty, widen by removing level.
        widened_from_level: Optional[str] = None
        if not recommendations and not intent.get("is_listing_query") and effective_filters.get("level"):
            original_level = str(effective_filters["level"])
            level_widened_profile = dict(profile)
            level_widened_profile["study_level"] = None
            level_widened_filters = dict(effective_filters)
            level_widened_filters["level"] = None
            level_widened_programs = self.retrieval.search_programs(
                query=retrieval_query,
                filters=level_widened_filters,
                profile=level_widened_profile,
            )
            level_widened_recs = self.recommender.generate(level_widened_profile, level_widened_programs, limit=5)
            if level_widened_recs:
                recommendations = level_widened_recs
                citation_programs = level_widened_programs
                widened_from_level = self._display_level(original_level)

        # If language filter is active and results are still empty, widen by removing language.
        widened_from_language: Optional[str] = None
        if not recommendations and not intent.get("is_listing_query") and effective_filters.get("language"):
            original_language = str(effective_filters["language"])
            lang_widened_profile = dict(profile)
            lang_widened_profile["language"] = None
            lang_widened_filters = dict(effective_filters)
            lang_widened_filters["language"] = None
            lang_widened_programs = self.retrieval.search_programs(
                query=retrieval_query,
                filters=lang_widened_filters,
                profile=lang_widened_profile,
            )
            lang_widened_recs = self.recommender.generate(lang_widened_profile, lang_widened_programs, limit=5)
            if lang_widened_recs:
                recommendations = lang_widened_recs
                citation_programs = lang_widened_programs
                widened_from_language = self._display_language(original_language)

        # If study_pace filter is active and results are still empty, widen by removing pace.
        widened_from_pace: Optional[str] = None
        if not recommendations and not intent.get("is_listing_query") and effective_filters.get("study_pace"):
            pace_widened_profile = dict(profile)
            pace_widened_profile["study_pace"] = None
            pace_widened_filters = dict(effective_filters)
            pace_widened_filters["study_pace"] = None
            pace_widened_programs = self.retrieval.search_programs(
                query=retrieval_query,
                filters=pace_widened_filters,
                profile=pace_widened_profile,
            )
            pace_widened_recs = self.recommender.generate(pace_widened_profile, pace_widened_programs, limit=5)
            if pace_widened_recs:
                recommendations = pace_widened_recs
                citation_programs = pace_widened_programs
                widened_from_pace = str(effective_filters["study_pace"])

        active_filters = {
            "city": profile.get("preferred_cities")[0] if profile.get("preferred_cities") else "",
            "level": (profile.get("study_level") or "").capitalize(),
            "language": (profile.get("language") or "").capitalize(),
            "study_pace": (profile.get("study_pace") or "").replace("-", " ").capitalize(),
        }

        if recommendations:
            lead = recommendations[0]
            if widened_from_city:
                filter_summary = self._listing_filter_summary(profile)
                if lang == "en":
                    if filter_summary:
                        answer = (
                            f"No programs found in {widened_from_city} matching {filter_summary} — "
                            f"here are the best matches from all of Sweden instead. "
                            f"Top match is {lead.program} at {lead.university}."
                        )
                    else:
                        answer = (
                            f"No programs found in {widened_from_city} matching your profile — "
                            f"here are the best matches from all of Sweden instead. "
                            f"Top match is {lead.program} at {lead.university}."
                        )
                else:
                    if filter_summary:
                        answer = (
                            f"Hittade inga program i {widened_from_city} som matchar {filter_summary} — "
                            f"här är de bästa matchningarna från hela Sverige i stället. "
                            f"Toppmatch är {lead.program} vid {lead.university}."
                        )
                    else:
                        answer = (
                            f"Hittade inga program i {widened_from_city} som matchar din profil — "
                            f"här är de bästa matchningarna från hela Sverige i stället. "
                            f"Toppmatch är {lead.program} vid {lead.university}."
                        )
            elif widened_from_level:
                if lang == "en":
                    answer = (
                        f"No {widened_from_level} programmes found matching your query — "
                        f"here are the best matches across all levels instead. "
                        f"Top match is {lead.program} at {lead.university}."
                    )
                else:
                    answer = (
                        f"Inga {widened_from_level}program hittades för din fråga — "
                        f"här är de bästa matchningarna oavsett nivå i stället. "
                        f"Toppmatch är {lead.program} vid {lead.university}."
                    )
            elif widened_from_language:
                if lang == "en":
                    answer = (
                        f"No programmes in {widened_from_language} found matching your query — "
                        f"here are the best matches regardless of language instead. "
                        f"Top match is {lead.program} at {lead.university}."
                    )
                else:
                    answer = (
                        f"Inga program på {widened_from_language} hittades för din fråga — "
                        f"här är de bästa matchningarna oavsett språk i stället. "
                        f"Toppmatch är {lead.program} vid {lead.university}."
                    )
            elif widened_from_pace:
                pace_label = widened_from_pace.replace("part-time", "deltid").replace("full-time", "heltid")
                if lang == "en":
                    answer = (
                        f"No {widened_from_pace} programmes found matching your query — "
                        f"here are the best matches regardless of study pace instead. "
                        f"Top match is {lead.program} at {lead.university}."
                    )
                else:
                    answer = (
                        f"Inga program på {pace_label} hittades för din fråga — "
                        f"här är de bästa matchningarna oavsett studietakt i stället. "
                        f"Toppmatch är {lead.program} vid {lead.university}."
                    )
            elif intent.get("is_listing_query") and active_filters.get("city"):
                city_label = self._display_city(active_filters["city"])
                filter_summary = self._listing_filter_summary(profile)
                if lang == "en":
                    noun = "programme" if len(recommendations) == 1 else "programmes"
                    if filter_summary:
                        if city_label == "distans":
                            answer = f"Here are {len(recommendations)} {noun} I found online matching {filter_summary}."
                        else:
                            answer = f"Here are {len(recommendations)} {noun} I found in {city_label} matching {filter_summary}."
                    else:
                        if city_label == "distans":
                            answer = f"Here are {len(recommendations)} {noun} I found online."
                        else:
                            answer = f"Here are {len(recommendations)} {noun} I found in {city_label}."
                else:
                    noun = "utbildning" if len(recommendations) == 1 else "utbildningar"
                    if filter_summary:
                        if city_label == "distans":
                            answer = f"Här är {len(recommendations)} {noun} jag hittade på distans som matchar {filter_summary}."
                        else:
                            answer = f"Här är {len(recommendations)} {noun} jag hittade i {city_label} som matchar {filter_summary}."
                    else:
                        if city_label == "distans":
                            answer = f"Här är {len(recommendations)} {noun} jag hittade på distans."
                        else:
                            answer = f"Här är {len(recommendations)} {noun} jag hittade i {city_label}."
            else:
                if lang == "en":
                    answer = f"Here are some programmes that match your profile. Top match right now is {lead.program} at {lead.university}."
                else:
                    answer = f"Här är några program som matchar din profil. Toppmatch just nu är {lead.program} vid {lead.university}."
        else:
            broadening_hint = self._location_broadening_hint(profile)
            broadening_hint_en = (
                " If you'd like, I can broaden the search to more cities or all of Sweden."
                if broadening_hint else ""
            )
            if intent.get("is_listing_query") and active_filters.get("city"):
                city_label = self._display_city(active_filters["city"])
                filter_summary = self._listing_filter_summary(profile)
                if lang == "en":
                    if filter_summary:
                        if city_label == "distans":
                            answer = f"I couldn't find any clear programmes online matching {filter_summary} right now.{broadening_hint_en}"
                        else:
                            answer = f"I couldn't find any clear programmes in {city_label} matching {filter_summary} right now.{broadening_hint_en}"
                    else:
                        if city_label == "distans":
                            answer = f"I couldn't find any clear programmes online right now.{broadening_hint_en}"
                        else:
                            answer = f"I couldn't find any clear programmes in {city_label} right now.{broadening_hint_en}"
                else:
                    if filter_summary:
                        if city_label == "distans":
                            answer = (
                                f"Jag hittade inga tydliga utbildningar på distans som matchar {filter_summary} just nu."
                                f"{broadening_hint}"
                            )
                        else:
                            answer = (
                                f"Jag hittade inga tydliga utbildningar i {city_label} som matchar {filter_summary} just nu."
                                f"{broadening_hint}"
                            )
                    else:
                        if city_label == "distans":
                            answer = (
                                "Jag hittade inga tydliga utbildningar på distans just nu."
                                f"{broadening_hint}"
                            )
                        else:
                            answer = (
                                f"Jag hittade inga tydliga utbildningar i {city_label} just nu."
                                f"{broadening_hint}"
                            )
            else:
                scope = self._scope_label(profile)
                focus = self._focus_label(profile)
                filter_summary = self._listing_filter_summary(profile)
                if lang == "en":
                    if focus:
                        answer = f"I couldn't find clear matches for the {focus} track yet.{broadening_hint_en}"
                    elif filter_summary:
                        answer = f"I couldn't find clear matches matching {filter_summary} yet.{broadening_hint_en}"
                    else:
                        answer = self.guidance_policy.build_no_match_answer(intent, lang=lang)
                else:
                    if focus:
                        answer = (
                            f"Jag hittade inga tydliga matchningar {scope} för spåret {focus} ännu."
                            f"{broadening_hint}"
                        )
                    elif filter_summary:
                        answer = (
                            f"Jag hittade inga tydliga matchningar {scope} som passar {filter_summary} ännu."
                            f"{broadening_hint}"
                        )
                    else:
                        answer = self.guidance_policy.build_no_match_answer(intent, lang=lang)

        citations = self._build_citations(citation_programs, recommendations)

        return ChatResponse(
            answer=answer,
            questions=[],
            recommendations=recommendations,
            citations=citations,
            active_filters=active_filters,
        )
