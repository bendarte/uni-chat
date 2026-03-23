from typing import Any, Dict

from app.services.guidance_taxonomy import DOMAIN_DISPLAY_LABELS


class GuidancePolicy:
    @staticmethod
    def build_retrieval_filters(intent: Dict[str, Any]) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        domains = intent.get("domains") or []
        if domains:
            filters["_domains"] = domains[:3]
        elif intent.get("domain"):
            # Only use strict single-domain filter when no multi-domain list is available
            filters["_domain"] = intent["domain"]
        if intent.get("career_track_candidates"):
            filters["_tracks"] = intent["career_track_candidates"][:3]
        return filters

    @staticmethod
    def should_clarify(intent: Dict[str, Any]) -> bool:
        if intent.get("is_listing_query"):
            return False
        if intent.get("is_comparison_query"):
            return True
        if intent.get("needs_clarification"):
            return True
        return bool(intent.get("domain") and (intent.get("is_vague") or intent.get("is_exploratory")))

    @staticmethod
    def build_clarification_answer(intent: Dict[str, Any], lang: str = "sv") -> str:
        en = lang == "en"
        if intent.get("comparison_answer"):
            suffix = (
                " I want to narrow down which side of that difference actually suits you best before recommending programmes."
                if en else
                " Jag vill smalna av vilken sida av den skillnaden som faktiskt passar dig bäst innan jag rekommenderar program."
            )
            return f"{intent['comparison_answer']}{suffix}"
        if intent.get("clarification_answer"):
            text = intent.get("clarification_answer_en", intent["clarification_answer"]) if en else intent["clarification_answer"]
            suffix = (
                " I'm asking because different study tracks lead to quite different everyday lives and careers."
                if en else
                " Jag frågar så här eftersom olika utbildningsspår leder till ganska olika vardag och karriärvägar."
            )
            return f"{text}{suffix}"
        if intent.get("is_exploratory") and intent.get("bridge_path_suggestions"):
            paths = ", ".join(path["label"] for path in intent["bridge_path_suggestions"][:3])
            if en:
                return (
                    "It sounds like you're exploring a combination of interests rather than a specific programme name. "
                    f"Some reasonable study tracks to start with are {paths}. "
                    "I need to narrow down which of those tracks suits you best before recommending programmes."
                )
            return (
                "Det låter som att du utforskar en kombination av intressen snarare än ett färdigt programnamn. "
                f"Några rimliga utbildningsspår att börja med är {paths}. "
                "Jag behöver smalna av vilket av de spåren som passar dig bäst innan jag rekommenderar program. "
                "Jag frågar på den nivån först för att inte gissa för tidigt."
            )
        label = DOMAIN_DISPLAY_LABELS.get(intent.get("domain") or "other", "olika utbildningsområden" if not en else "various fields")
        if en:
            return (
                f"It sounds like you're interested in {label}. "
                "Before I recommend programmes, I need to narrow down which type of study track suits you best."
            )
        return (
            f"Det låter som att du är intresserad av {label}. "
            "Innan jag rekommenderar program behöver jag smalna av vilken typ av utbildningsspår som passar dig bäst."
        )

    @staticmethod
    def build_no_match_answer(intent: Dict[str, Any], lang: str = "sv") -> str:
        en = lang == "en"
        domain = intent.get("domain")
        if domain:
            label = DOMAIN_DISPLAY_LABELS.get(domain, domain)
            if en:
                return (
                    f"I couldn't find any clear matches in {label} yet. "
                    "Try specifying a level, city, or which track within the field interests you most."
                )
            return (
                f"Jag hittade inga tydliga matchningar inom {label} ännu. "
                "Prova att ange nivå, stad eller vilket spår inom området som lockar mest."
            )
        if en:
            return "I couldn't find any clear matches yet. Try adjusting the city, level, or language."
        return "Jag hittade inga tydliga matchningar ännu. Prova att justera stad, nivå eller språk."
