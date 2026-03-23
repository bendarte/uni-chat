from typing import Any, Dict, List

from app.schemas import RecommendationItem
from app.services.explanation_service import ExplanationService
from app.services.language_normalization import infer_topics_from_text
from app.services.source_validation import is_valid_source_url, normalize_source_url

# Minimum rerank score for a program to be included in results.
_MIN_SCORE = 0.30

# A softer threshold: once 3 results have been collected, only include programs
# scoring above this to avoid padding the list with weak matches.
_SOFT_MIN_SCORE = 0.40

# Minimum interest-alignment score when the user has expressed interests.
# Programs below this are almost certainly off-topic.
_MIN_ALIGNMENT = 0.05

# Maximum number of course-like results to include before switching to programs only.
_MAX_COURSE_RESULTS = 2

# Hard cap on number of recommendations returned.
_MAX_RESULTS = 5


class RecommendationService:
    def __init__(self) -> None:
        self.explainer = ExplanationService()

    @staticmethod
    def _focus_text(program: Dict[str, Any]) -> str:
        return " ".join(
            [
                str(program.get("name", "")),
                str(program.get("field", "")),
            ]
        ).strip().lower()

    @staticmethod
    def _contains_any(text: str, markers: List[str]) -> bool:
        return any(marker in text for marker in markers)

    @staticmethod
    def _profile_topics(user_profile: Dict[str, Any]) -> set[str]:
        return {
            str(topic).strip().lower()
            for topic in infer_topics_from_text(
                *[str(item) for item in user_profile.get("interests", [])],
                *[str(item).replace("_", " ") for item in user_profile.get("current_tracks", [])],
                str(user_profile.get("current_domain") or ""),
            )
            if str(topic).strip()
        }

    @staticmethod
    def _program_topics(program: Dict[str, Any]) -> set[str]:
        return {
            str(topic).strip().lower()
            for topic in infer_topics_from_text(
                str(program.get("name") or ""),
                str(program.get("field") or ""),
                str(program.get("description") or ""),
                str(program.get("career_paths") or ""),
            )
            if str(topic).strip()
        }

    @classmethod
    def _passes_topic_guardrails(
        cls,
        user_profile: Dict[str, Any],
        program: Dict[str, Any],
        alignment: float,
    ) -> bool:
        profile_topics = cls._profile_topics(user_profile)
        if not profile_topics:
            return True

        program_topics = cls._program_topics(program)
        if profile_topics & program_topics:
            return True

        # Only apply the tech-topic guardrail when the user is clearly in a tech context.
        # If the domain is business, "analys" / "data science" in inferred topics is noise —
        # don't use it to block economics/finance programs.
        current_domain = str(user_profile.get("current_domain") or "").strip().lower()
        tech_topics = {"artificial intelligence", "data science", "computer science", "engineering"}
        if profile_topics & tech_topics and current_domain not in {"business", ""}:
            return bool(program_topics & tech_topics)

        return alignment >= 0.12

    @classmethod
    def _passes_track_guardrails(
        cls,
        program: Dict[str, Any],
        current_tracks: set[str],
    ) -> bool:
        if not current_tracks:
            return True

        focus_text = cls._focus_text(program)
        if "ai_data" in current_tracks:
            positive_markers = [
                " ai",
                "ai ",
                "artificial intelligence",
                "data science",
                "machine learning",
                "analytics",
                "informatik",
            ]
            negative_markers = [
                "social science",
                "neuroscience",
                "psychology",
                "brain",
            ]
            has_positive = any(marker in focus_text for marker in positive_markers)
            has_negative = any(marker in focus_text for marker in negative_markers)
            if not has_positive:
                return False
            if has_negative and "data science" not in focus_text and "artificial intelligence" not in focus_text:
                return False

        if "business_analytics" in current_tracks:
            positive_markers = [
                "business analytics",
                "analytics",
                "analysis",
                "data",
                "business intelligence",
                "information systems",
                "digital business",
                "informatics",
                "information management",
                "decision support",
                "economics",
                "ekonomi",
                "finance",
                "finans",
                "accounting",
                "redovisning",
                "management",
            ]
            negative_markers = [
                "fashion",
                "fine arts",
                "music",
                "film",
            ]
            has_positive = cls._contains_any(focus_text, positive_markers)
            has_negative = cls._contains_any(focus_text, negative_markers)
            if not has_positive:
                return False
            if has_negative and "analytics" not in focus_text and "data" not in focus_text:
                return False

        if "product_management" in current_tracks:
            positive_markers = [
                "product management",
                "produktledning",
                "digital leadership",
                "technology management",
                "innovation",
                "business design",
                "digital transformation",
                "information systems",
                "business development",
                "entrepreneurship",
            ]
            tech_markers = [
                "digital",
                "technology",
                "tech",
                "systems",
                "innovation",
                "product",
                "information systems",
            ]
            negative_markers = [
                "accounting",
                "retail",
                "fashion",
                "music",
                "fine arts",
            ]
            has_positive = cls._contains_any(focus_text, positive_markers)
            has_tech_marker = cls._contains_any(focus_text, tech_markers)
            has_negative = cls._contains_any(focus_text, negative_markers)
            if not has_positive:
                return False
            if "product management" not in focus_text and not has_tech_marker:
                return False
            if has_negative and not has_tech_marker:
                return False

        return True

    @staticmethod
    def _looks_like_course(program: Dict[str, Any], source_url: str) -> bool:
        name = str(program.get("name", "")).strip().lower()
        if "/coursecatalogue/" in source_url.lower() or "/course/" in source_url.lower():
            return True
        if any(marker in name for marker in [" english i", " english ii", " part i", " part ii"]):
            return True
        if name.startswith("english ") or name.endswith(" i") or name.endswith(" ii"):
            return True
        return False

    def generate(
        self,
        user_profile: Dict[str, Any],
        programs: List[Dict[str, Any]],
        limit: int = 5,
    ) -> List[RecommendationItem]:
        items: List[RecommendationItem] = []
        seen = set()
        current_domains = {
            str(d).strip().lower()
            for d in (user_profile.get("current_domains") or [user_profile.get("current_domain")] or [])
            if str(d or "").strip()
        }
        current_tracks = {
            str(track).strip().lower()
            for track in (user_profile.get("current_tracks") or [])
            if str(track).strip()
        }
        for program in programs:
            source_url = normalize_source_url(program.get("source_url"))
            if not is_valid_source_url(source_url):
                continue

            program_domains = {
                str(domain).strip().lower()
                for domain in (program.get("domains") or [])
                if str(domain).strip()
            }
            program_tracks = {
                str(track).strip().lower()
                for track in (program.get("tracks") or [])
                if str(track).strip()
            }

            # Block only if program has explicit domains that don't intersect any of the user's domains
            if current_domains and program_domains and not (program_domains & current_domains):
                continue
            if current_tracks and program_tracks and not (program_tracks & current_tracks):
                continue
            if not self._passes_track_guardrails(program, current_tracks):
                continue

            score = float(program.get("rerank_score", 0.0))
            alignment = float(program.get("alignment_score", 0.0))
            if user_profile.get("interests") and alignment < _MIN_ALIGNMENT:
                continue
            if not self._passes_topic_guardrails(user_profile, program, alignment):
                continue
            if score < _MIN_SCORE:
                continue
            if score < _SOFT_MIN_SCORE and len(items) >= 3:
                continue
            if self._looks_like_course(program, source_url) and len(items) >= _MAX_COURSE_RESULTS:
                continue
            dedupe_key = (
                str(program.get("name", "")).strip().lower(),
                str(program.get("university", "")).strip().lower(),
                str(program.get("city", "")).strip().lower(),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            explanation_payload = self.explainer.generate_program_explanation(
                user_profile=user_profile,
                program=program,
            )
            program_id = str(program.get("program_id", ""))
            source_id = str(explanation_payload.get("source_id") or f"ref-{program_id[:8]}")
            recommendation = RecommendationItem(
                program_id=program_id,
                source_id=source_id,
                program=explanation_payload.get("program", program.get("name", "")),
                university=explanation_payload.get("university", program.get("university", "")),
                city=program.get("city"),
                explanation=explanation_payload.get("explanation", []),
                source=source_url,
                score=score,
            )
            items.append(recommendation)
            if len(items) >= limit:
                break

        return items
