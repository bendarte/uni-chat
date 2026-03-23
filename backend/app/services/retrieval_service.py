import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from openai import OpenAI
from qdrant_client.models import FieldCondition, Filter, HasIdCondition, MatchAny, MatchValue
from sqlalchemy import and_, func, or_

from app.config import settings
from app.db import SessionLocal
from app.models import Program
from app.qdrant_client import PROGRAMS_COLLECTION_NAME, ensure_program_collection, get_qdrant_client
from app.services.guidance_tagging import annotate_guidance_item
from app.services.language_normalization import (
    expand_interests_with_synonyms,
    infer_topics_from_text,
    normalize_interests,
)
from app.services.metadata_normalization import (
    city_filter_values,
    normalize_city,
    normalize_language,
    normalize_study_pace,
    normalize_university,
    university_filter_values,
)
from app.services.source_validation import is_valid_source_url, normalize_source_url


class RetrievalService:
    # --- Scoring weights ---
    # Base score: blend of vector similarity and keyword match.
    _W_VECTOR = 0.7
    _W_KEYWORD = 0.3

    # Fallback scoring (no LLM available): weights for each signal.
    _W_FALLBACK_BASE = 0.30
    _W_FALLBACK_ALIGNMENT = 0.20
    _W_FALLBACK_TOPIC = 0.25
    _W_FALLBACK_PROGRAMNESS = 0.25

    # LLM-assisted scoring: the LLM score replaces most of the base signal.
    # Programness gets a dedicated weight to penalise course-like results regardless
    # of what the LLM scores.
    _W_LLM_SCORE = 0.35
    _W_LLM_ALIGNMENT = 0.20
    _W_LLM_TOPIC = 0.20
    _W_LLM_BASE = 0.10
    _W_LLM_PROGRAMNESS = 0.15

    # Alignment penalties applied when interest terms are present but not matched.
    _PENALTY_NO_MATCH = 0.35   # alignment ≤ 0.01
    _PENALTY_WEAK_MATCH = 0.55  # alignment ≤ 0.08

    # Penalty multiplier for items that look like individual courses rather than programmes.
    _PENALTY_COURSE = 0.75

    KEYWORD_STOPWORDS = {
        "i",
        "want",
        "study",
        "something",
        "with",
        "and",
        "or",
        "in",
        "the",
        "a",
        "an",
        "to",
        "of",
        "for",
        "jag",
        "vill",
        "plugga",
        "något",
        "nagot",
        "med",
        "och",
        "som",
        "bachelor",
        "master",
        "masters",
        "bachelors",
        "sweden",
        "sverige",
        "english",
        "swedish",
    }

    def __init__(self) -> None:
        self.logger = logging.getLogger("uvicorn.error")
        self.qdrant = get_qdrant_client()
        self.client = OpenAI(api_key=settings.openai_api_key, timeout=12.0, max_retries=0) if settings.openai_api_key else None
        ensure_program_collection()

    def create_embedding(self, text: str) -> List[float]:
        if not self.client:
            raise ValueError("OPENAI_API_KEY is required for embeddings")

        response = self.client.embeddings.create(
            model=settings.openai_embedding_model,
            input=text,
        )
        return response.data[0].embedding

    @staticmethod
    def _normalize_value(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return str(value).strip().lower()

    @staticmethod
    def _normalize_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        filters = dict(filters or {})
        filters["_city_locked"] = bool(filters.get("_city_locked"))
        cities = filters.get("cities") or []
        filters["cities"] = [
            normalize_city(str(city)) or str(city).strip().title()
            for city in cities
            if str(city).strip()
        ]
        universities = filters.get("universities") or []
        filters["universities"] = [
            normalize_university(str(university)) or str(university).strip()
            for university in universities
            if str(university).strip()
        ]
        exclude_universities = filters.get("exclude_universities") or []
        filters["exclude_universities"] = [
            normalize_university(str(university)) or str(university).strip()
            for university in exclude_universities
            if str(university).strip()
        ]
        filters["level"] = RetrievalService._normalize_value(filters.get("level"))
        filters["language"] = normalize_language(filters.get("language"))
        filters["study_pace"] = normalize_study_pace(filters.get("study_pace"))
        return filters

    @staticmethod
    def _build_effective_filters(
        request_filters: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        effective = dict(request_filters)

        profile_cities = [
            normalize_city(str(c)) or str(c).strip().title()
            for c in profile.get("preferred_cities", [])
            if str(c).strip()
        ]
        if profile_cities and not effective.get("cities"):
            effective["cities"] = profile_cities

        if not effective.get("level") and profile.get("study_level"):
            effective["level"] = str(profile["study_level"]).strip().lower()

        if not effective.get("language") and profile.get("language"):
            effective["language"] = normalize_language(profile["language"])

        if not effective.get("study_pace") and profile.get("study_pace"):
            effective["study_pace"] = normalize_study_pace(profile["study_pace"])

        return effective

    @staticmethod
    def _has_strict_filters(filters: Dict[str, Any]) -> bool:
        return bool(
            filters.get("cities")
            or filters.get("universities")
            or filters.get("exclude_universities")
            or filters.get("level")
            or filters.get("language")
            or filters.get("study_pace")
        )

    @staticmethod
    def _passes_filters(item: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        if not filters:
            return True

        cities = filters.get("cities") or []
        if cities:
            item_city = normalize_city(item.get("city"))
            if not item_city or item_city not in set(cities):
                return False

        universities = filters.get("universities") or []
        if universities:
            item_university = normalize_university(item.get("university"))
            if not item_university or item_university not in set(universities):
                return False

        excluded_universities = filters.get("exclude_universities") or []
        if excluded_universities:
            item_university = normalize_university(item.get("university"))
            if item_university and item_university in set(excluded_universities):
                return False

        level = filters.get("level")
        if level:
            item_level = str(item.get("level", "")).strip().lower()
            if not item_level or item_level != level:
                return False

        language = filters.get("language")
        if language:
            item_language = normalize_language(item.get("language"))
            if not item_language or item_language != language:
                return False

        study_pace = filters.get("study_pace")
        if study_pace:
            item_study_pace = normalize_study_pace(item.get("study_pace"))
            if not item_study_pace or item_study_pace != study_pace:
                return False

        domain_filter = filters.get("_domain")
        if domain_filter:
            item_domains = set(item.get("domains", []))
            if domain_filter not in item_domains:
                return False

        domain_filters = set(filters.get("_domains") or [])
        if domain_filters:
            item_domains = set(item.get("domains", []))
            if item_domains and not (item_domains & domain_filters):
                return False

        track_filters = set(filters.get("_tracks") or [])
        if track_filters:
            item_tracks = set(item.get("tracks", []))
            # Only block if the program has explicit tracks that conflict with the filter.
            # Programs without track annotation pass through (domain filter already handles domain matching).
            if item_tracks and not (item_tracks & track_filters):
                return False

        return True

    @staticmethod
    def _guidance_text(item: Dict[str, Any]) -> str:
        return " ".join(
            [
                str(item.get("name", "")),
                str(item.get("university", "")),
                str(item.get("field", "")),
                str(item.get("description", "")),
                str(item.get("career_paths", "")),
            ]
        ).lower()

    @classmethod
    def _annotate_guidance(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        return annotate_guidance_item(item)

    def _llm_expand_query(self, query: str) -> str:
        """Use GPT-4o-mini to expand a short user query into a richer semantic search phrase.

        Turns e.g. "jag vill bli lärare" into a query that includes program names,
        fields, career titles, and related subjects — giving the embedding model a
        much better signal for cosine similarity search.  Falls back silently to the
        original query if the LLM is unavailable or times out.
        """
        if not self.client or not query.strip():
            return query
        if len(query.split()) > 25:
            return query

        try:
            resp = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You help find university programmes. "
                            "Given the user's query about what they want to study or become, "
                            "expand it with related programme names, academic fields, career titles, "
                            "and subject keywords. Reply in the same language (Swedish/English) as the query. "
                            "Output ONLY the expanded terms — no explanation, no bullet points. Max 60 words."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                max_tokens=80,
                temperature=0.1,
                timeout=5.0,
            )
            expansion = resp.choices[0].message.content.strip()
            return f"{query} {expansion}" if expansion else query
        except Exception as exc:
            self.logger.warning("LLM query expansion failed, using original query: %s", exc)
            return query

    @staticmethod
    def _build_expanded_query(query: str, profile: Dict[str, Any]) -> str:
        interests = ", ".join(profile.get("interests", []) or []) or "not specified"
        preferred_cities = ", ".join(profile.get("preferred_cities", []) or []) or "not specified"
        study_level = str(profile.get("study_level") or "not specified")
        language = str(profile.get("language") or "not specified")
        study_pace = str(profile.get("study_pace") or "not specified")

        return (
            f"User interests: {interests}\n"
            f"Preferred cities: {preferred_cities}\n"
            f"Study level: {study_level}\n"
            f"Language: {language}\n"
            f"Study pace: {study_pace}\n\n"
            f"User message:\n{query}"
        )

    # Short domain abbreviations that are meaningful search terms despite being <= 2 chars.
    KEYWORD_SHORT_ALLOWLIST = {"it", "ai", "cs", "ux", "ml"}

    @classmethod
    def _extract_keyword_terms(cls, query: str) -> List[str]:
        raw_tokens = [token.strip().lower() for token in query.split() if token.strip()]
        terms = []
        seen = set()
        for token in raw_tokens:
            clean = "".join(ch for ch in token if ch.isalnum() or ch in {"-", "+"})
            if not clean:
                continue
            # Allow important short domain terms even though they are <= 2 chars.
            if clean in cls.KEYWORD_SHORT_ALLOWLIST:
                if clean not in seen:
                    seen.add(clean)
                    terms.append(clean)
                continue
            if len(clean) <= 2 or clean in cls.KEYWORD_STOPWORDS:
                continue
            if clean in seen:
                continue
            seen.add(clean)
            terms.append(clean)
            if len(terms) >= 20:
                break
        return terms

    @staticmethod
    def _build_interest_terms(profile: Dict[str, Any], query: str) -> List[str]:
        profile_interests = [str(i).strip().lower() for i in profile.get("interests", []) if str(i).strip()]
        query_interests = normalize_interests(query)
        combined = expand_interests_with_synonyms([*profile_interests, *query_interests])
        return combined[:25]

    @staticmethod
    def _interest_alignment_score(item: Dict[str, Any], interest_terms: List[str]) -> float:
        if not interest_terms:
            return 0.5

        text = " ".join(
            [
                str(item.get("name", "")),
                str(item.get("field", "")),
                str(item.get("description", "")),
                str(item.get("career_paths", "")),
            ]
        ).lower()
        if not text.strip():
            return 0.0

        hits = 0
        for term in interest_terms:
            token = term.strip().lower()
            if token and token in text:
                hits += 1

        return min(1.0, hits / max(len(interest_terms), 1))

    @staticmethod
    def _query_topics(profile: Dict[str, Any], query: str) -> List[str]:
        topics = infer_topics_from_text(
            query,
            *[str(item) for item in profile.get("interests", [])],
            *[str(item).replace("_", " ") for item in profile.get("current_tracks", [])],
            str(profile.get("current_domain") or ""),
        )
        seen = set()
        ordered: List[str] = []
        for topic in topics:
            clean = str(topic).strip().lower()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            ordered.append(clean)
        return ordered

    @staticmethod
    def _program_topics(item: Dict[str, Any]) -> List[str]:
        return infer_topics_from_text(
            str(item.get("name") or ""),
            str(item.get("field") or ""),
            str(item.get("description") or ""),
            str(item.get("career_paths") or ""),
        )

    @classmethod
    def _topic_overlap_score(
        cls,
        item: Dict[str, Any],
        query_topics: List[str],
        current_domains: Optional[List[str]] = None,
    ) -> float:
        if not query_topics:
            # Fall back to domain alignment when no specific topics were extracted
            # from the query. This prevents all programs from scoring identically
            # (0.5) when the user's intent is clear from domain context alone.
            if current_domains:
                item_domains = set(item.get("domains") or [])
                if item_domains:
                    if item_domains & set(current_domains):
                        return 0.8
                    elif "other" not in item_domains:
                        return 0.1
            return 0.5
        item_topics = {
            str(topic).strip().lower()
            for topic in cls._program_topics(item)
            if str(topic).strip()
        }
        if not item_topics:
            return 0.0
        overlap = item_topics & set(query_topics)
        if not overlap:
            return 0.0
        return min(1.0, len(overlap) / max(len(set(query_topics)), 1))

    @classmethod
    def _apply_specific_topic_guardrail(
        cls,
        item: Dict[str, Any],
        query_topics: List[str],
        current_tracks: List[str],
    ) -> float:
        if not query_topics:
            return 1.0

        item_topics = {
            str(topic).strip().lower()
            for topic in cls._program_topics(item)
            if str(topic).strip()
        }
        query_topic_set = set(query_topics)
        if item_topics & query_topic_set:
            return 1.0

        tech_topics = {"artificial intelligence", "data science", "computer science", "engineering"}
        if query_topic_set & tech_topics:
            if not item_topics:
                return 0.2
            if not (item_topics & tech_topics):
                return 0.08

        if "ai_data" in {str(track).strip().lower() for track in current_tracks if str(track).strip()}:
            focus_text = " ".join(
                [
                    str(item.get("name") or ""),
                    str(item.get("field") or ""),
                    str(item.get("description") or ""),
                ]
            ).lower()
            ai_markers = ["artificial intelligence", "machine learning", "data science", "ai ", " ai", "analytics"]
            if not any(marker in focus_text for marker in ai_markers):
                return 0.05

        return 0.35

    @staticmethod
    def _program_likelihood_score(item: Dict[str, Any]) -> float:
        name = str(item.get("name", "")).lower()
        source_url = str(item.get("source_url", "")).lower()
        field = str(item.get("field", "")).lower()

        strong_markers = ["programme", "program", "bachelor", "master", "degree"]
        weak_course_markers = ["course", "kurs", "english i", "english ii", "part i", "part ii"]

        score = 0.4
        if any(marker in name for marker in strong_markers):
            score = 1.0
        elif any(marker in source_url for marker in ["/program", "/programme", "/programmes"]):
            score = 0.95
        elif "/coursecatalogue/" in source_url or "/course/" in source_url:
            score = 0.25

        if any(marker in name for marker in weak_course_markers):
            score = min(score, 0.2)

        if field and any(marker in field for marker in ["education", "teaching"]):
            score = max(score, 0.35)

        return max(0.0, min(1.0, score))

    @staticmethod
    def _listing_relevance_score(item: Dict[str, Any], filters: Dict[str, Any]) -> float:
        name = str(item.get("name") or "").lower()
        field = str(item.get("field") or "").lower()
        level = str(item.get("level") or "").lower()
        study_pace = str(item.get("study_pace") or "").lower()

        score = 0.0

        broad_program_markers = [
            "business and economics",
            "economics",
            "computer science",
            "information and communication technology",
            "biomedicine",
            "biomedicinska analytiker",
            "arbetsterapeut",
            "psychology",
            "law",
            "international business",
            "mathematics",
            "engineering",
            "data science",
        ]
        niche_markers = [
            "with a specialization",
            "folk music",
            "art music",
            "individual programme",
            "fine arts",
            "opera",
            "music,",
            "performance",
        ]

        if any(marker in name for marker in broad_program_markers):
            score += 2.0
        if any(marker in field for marker in ["economics", "computer science", "health", "business", "law", "psychology"]):
            score += 1.0
        if any(marker in name for marker in niche_markers):
            score -= 2.0
        if "music" in field and "business" not in field and "economics" not in field:
            score -= 1.2

        if not filters.get("level"):
            if level == "bachelor":
                score += 1.0
            elif level == "master":
                score += 0.4

        if not filters.get("study_pace"):
            if study_pace == "full-time":
                score += 0.4
            elif study_pace == "part-time":
                score -= 0.2

        if len(name) <= 45:
            score += 0.2
        elif len(name) >= 90:
            score -= 0.2

        return score

    @staticmethod
    def _apply_sql_filters(query_obj, filters: Dict[str, Any]):
        cities = filters.get("cities") or []
        if cities:
            city_values = sorted(
                {
                    candidate
                    for city in cities
                    for candidate in city_filter_values(city)
                }
            )
            query_obj = query_obj.filter(func.lower(Program.city).in_(city_values))

        universities = filters.get("universities") or []
        if universities:
            university_values = sorted(
                {
                    candidate
                    for university in universities
                    for candidate in university_filter_values(university)
                }
            )
            query_obj = query_obj.filter(func.lower(Program.university).in_(university_values))

        excluded_universities = filters.get("exclude_universities") or []
        if excluded_universities:
            excluded_values = sorted(
                {
                    candidate
                    for university in excluded_universities
                    for candidate in university_filter_values(university)
                }
            )
            query_obj = query_obj.filter(~func.lower(Program.university).in_(excluded_values))

        if filters.get("level"):
            query_obj = query_obj.filter(func.lower(Program.level) == str(filters["level"]).lower())

        if filters.get("language"):
            query_obj = query_obj.filter(func.lower(Program.language) == str(filters["language"]).lower())

        if filters.get("study_pace"):
            query_obj = query_obj.filter(
                func.lower(Program.study_pace) == str(filters["study_pace"]).lower()
            )

        return query_obj

    def _filtered_program_ids(self, filters: Dict[str, Any], limit: int = 4000) -> Optional[List[str]]:
        if not self._has_strict_filters(filters):
            return None

        with SessionLocal() as db:
            query_obj = db.query(Program.id).filter(and_(Program.source_url.isnot(None), Program.source_url != ""))
            query_obj = self._apply_sql_filters(query_obj, filters)
            rows = query_obj.limit(limit).all()
        return [str(row.id) for row in rows]

    @staticmethod
    def _build_qdrant_filter(filters: Dict[str, Any], allowed_ids: Optional[List[str]]) -> Optional[Filter]:
        must = []

        if allowed_ids:
            must.append(HasIdCondition(has_id=allowed_ids))

        cities = filters.get("cities") or []
        if cities:
            if len(cities) == 1:
                must.append(FieldCondition(key="city", match=MatchValue(value=cities[0])))
            else:
                must.append(FieldCondition(key="city", match=MatchAny(any=cities)))

        if filters.get("level"):
            must.append(FieldCondition(key="level", match=MatchValue(value=filters["level"])))

        if filters.get("language"):
            must.append(FieldCondition(key="language", match=MatchValue(value=filters["language"])))

        if filters.get("study_pace"):
            must.append(FieldCondition(key="study_pace", match=MatchValue(value=filters["study_pace"])))

        return Filter(must=must) if must else None

    def _vector_search(
        self,
        query: str,
        filters: Dict[str, Any],
        profile: Dict[str, Any],
        limit: int = 20,
        allowed_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.client:
            return []
        if allowed_ids == []:
            return []

        llm_query = self._llm_expand_query(query)
        expanded_query = self._build_expanded_query(query=llm_query, profile=profile)
        query_vector = self.create_embedding(expanded_query)
        results = self.qdrant.search(
            collection_name=PROGRAMS_COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=self._build_qdrant_filter(filters, allowed_ids),
            limit=limit,
            with_payload=True,
        )

        candidates: List[Dict[str, Any]] = []
        for point in results:
            payload = point.payload or {}
            item = {
                "program_id": str(payload.get("program_id") or point.id),
                "name": payload.get("name"),
                "university": payload.get("university"),
                "city": normalize_city(payload.get("city")),
                "country": payload.get("country"),
                "level": self._normalize_value(payload.get("level")),
                "language": normalize_language(payload.get("language")),
                "study_pace": normalize_study_pace(payload.get("study_pace")),
                "field": payload.get("field"),
                "description": payload.get("description", ""),
                "career_paths": payload.get("career_paths", ""),
                "source_url": normalize_source_url(payload.get("source_url", "")),
                "vector_score": float(point.score),
                "keyword_score": 0.0,
            }
            # Clear stale domain/track data from Qdrant to force re-inference
            # using the current (fixed) logic on every query.
            item.pop("domains", None)
            item.pop("tracks", None)
            item = self._annotate_guidance(item)
            if is_valid_source_url(item["source_url"]) and self._passes_filters(item, filters):
                candidates.append(item)

        return candidates

    def _keyword_search(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int = 40,
        allowed_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if allowed_ids == []:
            return []

        terms = self._extract_keyword_terms(query)
        candidates: List[Dict[str, Any]] = []

        with SessionLocal() as db:
            query_obj = db.query(Program).filter(and_(Program.source_url.isnot(None), Program.source_url != ""))
            query_obj = self._apply_sql_filters(query_obj, filters)

            if allowed_ids:
                query_obj = query_obj.filter(
                    Program.id.in_([uuid.UUID(program_id) for program_id in allowed_ids])
                )

            if terms:
                term_conditions = []
                for term in terms:
                    like = f"%{term}%"
                    term_conditions.append(
                        or_(
                            Program.name.ilike(like),
                            Program.description.ilike(like),
                            Program.career_paths.ilike(like),
                            Program.field.ilike(like),
                            Program.university.ilike(like),
                        )
                    )
                query_obj = query_obj.filter(or_(*term_conditions))

            rows = query_obj.limit(limit).all()

            if not rows and not terms:
                rows = query_obj.order_by(Program.last_updated.desc()).limit(limit).all()

        query_terms = terms
        for row in rows:
            source_url = normalize_source_url(row.source_url)
            if not is_valid_source_url(source_url):
                continue

            haystack = " ".join(
                [
                    row.name or "",
                    row.description or "",
                    row.career_paths or "",
                    row.field or "",
                    row.university or "",
                    row.city or "",
                    row.study_pace or "",
                ]
            ).lower()
            overlap = sum(1 for term in query_terms if term in haystack)
            keyword_score = overlap / max(len(query_terms), 1)
            item = {
                "program_id": str(row.id),
                "name": row.name,
                "university": row.university,
                "city": normalize_city(row.city),
                "country": row.country,
                "level": self._normalize_value(row.level),
                "language": normalize_language(row.language),
                "study_pace": normalize_study_pace(row.study_pace),
                "field": row.field,
                "description": row.description,
                "career_paths": row.career_paths,
                "source_url": source_url,
                "vector_score": 0.0,
                "keyword_score": float(keyword_score),
            }
            # Domains/tracks come from DB rows which never stored them;
            # always infer fresh to use current logic.
            item = self._annotate_guidance(item)
            if self._passes_filters(item, filters):
                candidates.append(item)

        return candidates

    @staticmethod
    def _merge_results(vector_items: List[Dict[str, Any]], keyword_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for item in [*vector_items, *keyword_items]:
            key = item["program_id"]
            if key not in merged:
                merged[key] = item
                continue

            current = merged[key]
            current["vector_score"] = max(current.get("vector_score", 0.0), item.get("vector_score", 0.0))
            current["keyword_score"] = max(current.get("keyword_score", 0.0), item.get("keyword_score", 0.0))
            for field_name in (
                "name",
                "university",
                "city",
                "country",
                "level",
                "language",
                "study_pace",
                "field",
                "description",
                "career_paths",
                "source_url",
            ):
                if not current.get(field_name) and item.get(field_name):
                    current[field_name] = item[field_name]

        return list(merged.values())

    def _hydrate_results(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not items:
            return []

        id_map = {}
        for item in items:
            try:
                id_map[uuid.UUID(item["program_id"])] = item["program_id"]
            except Exception:
                continue

        if not id_map:
            return items

        with SessionLocal() as db:
            rows = db.query(Program).filter(Program.id.in_(list(id_map.keys()))).all()

        row_map = {str(row.id): row for row in rows}
        hydrated = []
        for item in items:
            row = row_map.get(item["program_id"])
            if row:
                item.update(
                    {
                        "name": row.name,
                        "university": row.university,
                        "city": normalize_city(row.city),
                        "country": row.country,
                        "level": self._normalize_value(row.level),
                        "language": normalize_language(row.language),
                        "study_pace": normalize_study_pace(row.study_pace),
                        "field": row.field,
                        "description": row.description,
                        "career_paths": row.career_paths,
                        "source_url": normalize_source_url(row.source_url),
                    }
                )
                # Clear any stale domain/track data before re-annotating with
                # fresh DB fields so the current inference logic is always used.
                item.pop("domains", None)
                item.pop("tracks", None)
                item = self._annotate_guidance(item)
            if is_valid_source_url(item.get("source_url")):
                hydrated.append(item)
        return hydrated

    def _rerank_with_llm(
        self,
        query: str,
        profile: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        interest_terms = self._build_interest_terms(profile=profile, query=query)
        query_topics = self._query_topics(profile=profile, query=query)
        current_tracks = [str(track).strip().lower() for track in (profile.get("current_tracks") or []) if str(track).strip()]
        current_domains = [str(d).strip().lower() for d in (profile.get("current_domains") or []) if str(d).strip()]

        if not self.client:
            for item in candidates:
                base = self._W_VECTOR * float(item.get("vector_score", 0.0)) + self._W_KEYWORD * float(item.get("keyword_score", 0.0))
                alignment = self._interest_alignment_score(item, interest_terms)
                topic_overlap = self._topic_overlap_score(item, query_topics, current_domains)
                programness = self._program_likelihood_score(item)
                final_score = self._W_FALLBACK_BASE * base + self._W_FALLBACK_ALIGNMENT * alignment + self._W_FALLBACK_TOPIC * topic_overlap + self._W_FALLBACK_PROGRAMNESS * programness
                item["alignment_score"] = round(alignment, 6)
                item["topic_overlap_score"] = round(topic_overlap, 6)
                if programness < 0.3:
                    final_score *= self._PENALTY_COURSE
                if interest_terms and alignment <= 0.01:
                    final_score *= self._PENALTY_NO_MATCH
                elif interest_terms and alignment <= 0.08:
                    final_score *= self._PENALTY_WEAK_MATCH
                final_score *= self._apply_specific_topic_guardrail(item, query_topics, current_tracks)
                item["rerank_score"] = round(final_score, 6)
            candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
            return candidates[:top_n]

        payload = [
            {
                "program_id": item["program_id"],
                "name": item.get("name"),
                "field": item.get("field"),
                "description": (item.get("description") or "")[:450],
                "career_paths": (item.get("career_paths") or "")[:300],
                "city": item.get("city"),
                "study_pace": item.get("study_pace"),
                "university": item.get("university"),
                "topical_alignment": round(self._interest_alignment_score(item, interest_terms), 6),
                "topic_overlap": round(self._topic_overlap_score(item, query_topics, current_domains), 6),
                "program_likelihood": round(self._program_likelihood_score(item), 6),
                "vector_score": item.get("vector_score", 0.0),
                "keyword_score": item.get("keyword_score", 0.0),
            }
            for item in candidates[:20]
        ]

        prompt = {
            "task": "rerank_study_programs",
            "instructions": "Prioritize: (1) user interests semantic match, (2) strict city/level/language/study pace fit, (3) career alignment.",
            "query": query,
            "user_profile": profile,
            "candidates": payload,
            "output_schema": {
                "scores": [{"program_id": "string", "score": "float between 0 and 1"}]
            },
        }

        try:
            response = self.client.chat.completions.create(
                model=settings.openai_chat_model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": "Return strict JSON only with key 'scores'. Do not add extra text.",
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                timeout=5.0,
            )
            content = (response.choices[0].message.content or "").strip()
            if content.startswith("```"):
                content = content.strip("`")
                if content.lower().startswith("json"):
                    content = content[4:].strip()
            parsed = json.loads(content)
            score_map = {
                str(item["program_id"]): float(item["score"])
                for item in parsed.get("scores", [])
                if "program_id" in item and "score" in item
            }
        except Exception as exc:
            self.logger.warning("LLM reranking fallback triggered: %s", exc)
            score_map = {}

        for item in candidates:
            base_score = self._W_VECTOR * float(item.get("vector_score", 0.0)) + self._W_KEYWORD * float(item.get("keyword_score", 0.0))
            alignment = self._interest_alignment_score(item, interest_terms)
            topic_overlap = self._topic_overlap_score(item, query_topics, current_domains)
            programness = self._program_likelihood_score(item)
            llm_score = float(score_map.get(item["program_id"], base_score))
            final_score = self._W_LLM_SCORE * llm_score + self._W_LLM_ALIGNMENT * alignment + self._W_LLM_TOPIC * topic_overlap + self._W_LLM_BASE * base_score + self._W_LLM_PROGRAMNESS * programness
            item["alignment_score"] = round(alignment, 6)
            item["topic_overlap_score"] = round(topic_overlap, 6)
            if interest_terms and alignment <= 0.01:
                final_score *= self._PENALTY_NO_MATCH
            elif interest_terms and alignment <= 0.08:
                final_score *= self._PENALTY_WEAK_MATCH
            if programness < 0.3:
                final_score *= self._PENALTY_COURSE
            final_score *= self._apply_specific_topic_guardrail(item, query_topics, current_tracks)
            item["rerank_score"] = round(float(final_score), 6)

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        return candidates[:top_n]

    def _search_once(
        self,
        query: str,
        filters: Dict[str, Any],
        profile: Dict[str, Any],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        allowed_ids = self._filtered_program_ids(filters)
        if allowed_ids == []:
            return []

        vector_items = self._vector_search(
            query=query,
            filters=filters,
            profile=profile,
            limit=max(top_n * 3, 20),
            allowed_ids=allowed_ids,
        )
        keyword_items = self._keyword_search(
            query=query,
            filters=filters,
            limit=max(top_n * 4, 40),
            allowed_ids=allowed_ids,
        )
        merged = self._hydrate_results(self._merge_results(vector_items, keyword_items))
        merged = [item for item in merged if self._passes_filters(item, filters)]
        return self._rerank_with_llm(query, profile, merged, top_n=top_n)

    def _expand_query_with_synonyms(self, query: str, profile: Dict[str, Any]) -> str:
        query_interests = normalize_interests(query)
        profile_interests = [str(i).strip().lower() for i in profile.get("interests", []) if str(i).strip()]
        seeds = query_interests + profile_interests
        expanded_topics = expand_interests_with_synonyms(seeds)

        if not expanded_topics and len(query.split()) <= 3:
            expanded_topics = ["technology", "engineering", "business"]

        extras = " ".join(expanded_topics)
        return f"{query} {extras}".strip()

    def search_programs(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        normalized_filters = self._build_effective_filters(self._normalize_filters(filters), profile)
        query = (query or "").strip()
        if not query:
            query = " ".join(profile.get("interests", []) or ["study program"]).strip()

        results = self._search_once(query=query, filters=normalized_filters, profile=profile, top_n=10)
        if results:
            return results

        expanded_query = self._expand_query_with_synonyms(query=query, profile=profile)
        results = self._search_once(
            query=expanded_query,
            filters=normalized_filters,
            profile=profile,
            top_n=10,
        )
        if results:
            return results

        if self._has_strict_filters(normalized_filters):
            return []

        return self._search_once(query=expanded_query, filters={}, profile=profile, top_n=10)

    def list_programs(
        self,
        filters: Optional[Dict[str, Any]],
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        normalized_filters = self._normalize_filters(filters)

        with SessionLocal() as db:
            query_obj = db.query(Program).filter(and_(Program.source_url.isnot(None), Program.source_url != ""))
            query_obj = self._apply_sql_filters(query_obj, normalized_filters)
            if self._has_strict_filters(normalized_filters):
                rows = query_obj.all()
            else:
                rows = (
                    query_obj.order_by(Program.last_updated.desc())
                    .limit(max(limit * 20, 200))
                    .all()
                )

        items: List[Dict[str, Any]] = []
        for row in rows:
            source_url = normalize_source_url(row.source_url)
            if not is_valid_source_url(source_url):
                continue

            item = {
                "program_id": str(row.id),
                "name": row.name,
                "university": row.university,
                "city": normalize_city(row.city),
                "country": row.country,
                "level": self._normalize_value(row.level),
                "language": normalize_language(row.language),
                "study_pace": normalize_study_pace(row.study_pace),
                "field": row.field,
                "description": row.description,
                "career_paths": row.career_paths,
                "source_url": source_url,
                "vector_score": 0.0,
                "keyword_score": 0.0,
                "rerank_score": 1.0,
                "alignment_score": 1.0,
            }
            item = self._annotate_guidance(item)
            if self._passes_filters(item, normalized_filters):
                items.append(item)

        items.sort(
            key=lambda item: (
                self._listing_relevance_score(item, normalized_filters),
                self._program_likelihood_score(item),
                str(item.get("university") or "").lower(),
                str(item.get("name") or "").lower(),
            ),
            reverse=True,
        )
        return items[:limit]
