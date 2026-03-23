import re
from typing import Any, Dict, List, Optional

from app.services.guidance_taxonomy import (
    BRIDGE_PATHS,
    DOMAIN_FOLLOW_UP_QUESTIONS,
    DOMAIN_KEYWORDS,
    MOTIVATION_GUIDANCE,
    SOCIETY_TECH_BRIDGE_PATHS,
    DOMAIN_SPECIFIC_ROLE_TERMS,
    TRACK_KEYWORDS,
)
from app.services.metadata_normalization import CITY_ALIASES


class IntentService:
    TOP_LEVEL_GUIDANCE_OPTIONS = [
        {
            "id": "top_business",
            "label": "Ekonomi & Business",
            "domains": ["business"],
            "tracks": [],
            "next_questions": [
                "Är du mest nyfiken på ekonomi, finans, affärsutveckling eller marknadsföring?",
                "Vill du ha ett brett affärsspår eller något mer analytiskt från början?",
            ],
        },
        {
            "id": "top_tech",
            "label": "IT & Teknik",
            "domains": ["tech"],
            "tracks": [],
            "next_questions": [
                "Lockar AI och data, systemutveckling, cybersäkerhet eller UX mest?",
                "Vill du ha ett mer tekniskt tungt spår eller något där teknik möter människor och verksamhet?",
            ],
        },
        {
            "id": "top_healthcare",
            "label": "Vård & Medicin",
            "domains": ["healthcare"],
            "tracks": [],
            "next_questions": [
                "Vill du arbeta patientnära, med diagnostik/labb eller med hälsa på ett bredare plan?",
                "Är det viktigast för dig att möta människor direkt eller att förstå medicin och hälsa mer analytiskt?",
            ],
        },
        {
            "id": "top_humanities",
            "label": "Humaniora & Samhälle",
            "domains": ["humanities"],
            "tracks": [],
            "next_questions": [
                "Lockar samhällsfrågor, historia, politik eller språk mest?",
                "Vill du arbeta mer med analys av samhälle, kultur och människor än med teknik eller affär?",
            ],
        },
        {
            "id": "top_education",
            "label": "Pedagogik & människor",
            "domains": ["education", "psychology_social"],
            "tracks": [],
            "next_questions": [
                "Är du mer intresserad av undervisning, psykologi eller stödjande arbete med människor?",
                "Vill du arbeta i skola, i rådgivande roller eller med socialt stöd?",
            ],
        },
        {
            "id": "top_creative",
            "label": "Kreativt & Media",
            "domains": ["art", "media_communication"],
            "tracks": [],
            "next_questions": [
                "Lockar design, media, kommunikation eller musik mest?",
                "Vill du att kreativitet ska stå i centrum, eller kombinera den med något mer strategiskt eller digitalt?",
            ],
        },
        {
            "id": "top_law_built",
            "label": "Juridik & samhällsbyggnad",
            "domains": ["law", "built_environment"],
            "tracks": [],
            "next_questions": [
                "Dras du mer mot juridik och regler, eller mot arkitektur, bygg och samhällsplanering?",
                "Vill du arbeta mer med bedömningar och regelverk eller med hur samhällen och miljöer utformas?",
            ],
        },
    ]

    COMPARISON_PATTERNS = [
        {
            "terms": ["systemvetenskap", "datateknik"],
            "domain": "tech",
            "answer": (
                "Det är en viktig skillnad. Systemvetenskap brukar ligga närmare verksamhet, digitala system och hur teknik används i organisationer, "
                "medan datateknik oftare är mer tekniskt och ingenjörsnära med större tyngd på hur systemen byggs."
            ),
            "questions": [
                "Lockar samspelet mellan verksamhet, människor och digitala system mer än den tekniska konstruktionen bakom systemen?",
                "Vill du ha ett mer ingenjörstungt spår eller ett spår som kombinerar teknik med organisation och affär?",
            ],
        },
        {
            "terms": ["systems science", "computer engineering"],
            "domain": "tech",
            "answer": (
                "Those are close on the surface, but they usually lead in different directions. Systems science is often more about organisations, digital systems and how technology is used, "
                "while computer engineering is usually more technical and engineering-heavy with more focus on how the systems are built."
            ),
            "questions": [
                "Are you more interested in how organisations use digital systems, or in the technical construction behind the systems?",
                "Do you want a more engineering-heavy path, or a path that combines technology with business and organisational thinking?",
            ],
        },
        {
            "terms": ["ekonomi", "industriell ekonomi"],
            "domain": "business",
            "answer": (
                "Det är ett vanligt vägval. Ekonomi brukar vara bredare mot företagsekonomi, nationalekonomi, finans och management, "
                "medan industriell ekonomi oftare kombinerar affär med teknik, optimering och verksamhetsutveckling."
            ),
            "questions": [
                "Vill du ha ett renare affärs- och ekonomispår, eller tycker du om att kombinera affär med teknik och problemlösning?",
                "Lockar finans, management och marknad mer än tekniknära analys och effektivisering?",
            ],
        },
        {
            "terms": ["psykologi", "socionom"],
            "domain": "psychology_social",
            "answer": (
                "Det är också en viktig skillnad. Psykologi ligger oftare närmare beteende, mental hälsa och förståelse av individer, "
                "medan socionomspåret brukar vara mer inriktat på stödinsatser, samhällsarbete och arbete i sociala verksamheter."
            ),
            "questions": [
                "Är du mer intresserad av att förstå människors beteende och mående, eller av att arbeta med stöd, insatser och samhällsstrukturer?",
                "Vill du hellre arbeta mer samtals- och individnära eller mer i välfärds- och myndighetsnära roller?",
            ],
        },
        {
            "terms": ["systemvetenskap", "informatik"],
            "domain": "tech",
            "answer": (
                "De ligger nära varandra, men informatik är ofta mer fokuserat på information, digitalisering och hur IT används i verksamheter, "
                "medan systemvetenskap ofta upplevs som bredare kring system, verksamhet och utveckling av digitala lösningar."
            ),
            "questions": [
                "Vill du gå mer mot digitalisering och informationshantering, eller mot bredare system och verksamhetsutveckling?",
                "Är det viktigast för dig att förstå hur organisationer använder IT, eller att arbeta bredare med digitala lösningar och system?",
            ],
        },
        {
            "terms": ["jurist", "ekonom"],
            "domain": "business",
            "answer": (
                "Det vägvalet handlar ofta om vilken typ av problem du vill arbeta med. Juristspåret kretsar mer kring regler, avtal och rättsliga bedömningar, "
                "medan ekonomispåret oftare handlar om företag, marknader, analys och affärsbeslut."
            ),
            "questions": [
                "Lockar regler, avtal och argumentation mer än siffror, analys och affärsfrågor?",
                "Vill du arbeta närmare juridiska bedömningar eller närmare företag och ekonomiska beslut?",
            ],
        },
        {
            "terms": ["beteendevetare", "psykolog"],
            "domain": "psychology_social",
            "answer": (
                "De ligger nära i intresseområde, men leder ofta till olika typer av roller. Psykologspåret är mer inriktat på psykologi som huvudämne och mer specialiserade yrkesvägar, "
                "medan beteendevetarspåret brukar vara bredare över psykologi, sociologi och pedagogik."
            ),
            "questions": [
                "Vill du gå djupare in i psykologi som huvudspår, eller ha en bredare samhälls- och beteendeinriktad utbildning?",
                "Är du mer ute efter en specialiserad profession eller en bred utbildning som kan leda till flera olika roller?",
            ],
        },
        {
            "terms": ["civilingenjör", "högskoleingenjör"],
            "domain": "tech",
            "answer": (
                "Det valet handlar ofta om både längd och tyngd. Civilingenjör brukar vara längre och mer teoretiskt eller strategiskt fördjupad, "
                "medan högskoleingenjör oftare är kortare och mer direkt tillämpad mot yrkesrollen."
            ),
            "questions": [
                "Vill du ha en längre utbildning med mer fördjupning, eller komma snabbare ut i arbetslivet med en mer tillämpad ingenjörsroll?",
                "Lockar teknisk bredd och möjligheten att läsa vidare mer än en mer direkt yrkesinriktad väg?",
            ],
        },
        {
            "terms": ["läkare", "biomedicin"],
            "domain": "healthcare",
            "answer": (
                "Det är två ganska olika riktningar trots att båda ligger nära medicin. Läkarspåret är tydligt patient- och kliniknära, "
                "medan biomedicin oftare ligger närmare laboratorier, forskning och den biologiska grunden bakom sjukdom och behandling."
            ),
            "questions": [
                "Vill du arbeta patientnära i klinisk vardag, eller känns labb, analys och forskning mer rätt för dig?",
                "Är du mer lockad av behandling och medicinska beslut, eller av att förstå mekanismerna bakom hälsa och sjukdom?",
            ],
        },
        {
            "terms": ["lärare", "socionom"],
            "domain": "education",
            "answer": (
                "Det valet handlar mycket om vilken vardag du vill ha. Lärarspåret är mer fokuserat på undervisning, lärande och arbete i skolmiljö, "
                "medan socionomspåret oftare handlar om stöd, sociala insatser och arbete i välfärds- eller myndighetsnära verksamheter."
            ),
            "questions": [
                "Vill du arbeta mer med lärande och klassrumssituationer, eller med stödinsatser och sociala frågor runt människor och familjer?",
                "Känns skolmiljön mer rätt för dig än socialt arbete och myndighetsnära roller?",
            ],
        },
        {
            "terms": ["arkitekt", "byggingenjör"],
            "domain": "built_environment",
            "answer": (
                "Det är ett klassiskt vägval inom samhällsbyggnad. Arkitektspåret ligger oftare närmare form, rum, gestaltning och hur människor upplever byggda miljöer, "
                "medan byggingenjör oftare är mer tekniskt och konstruktionsnära med fokus på hur byggnader projekteras, dimensioneras och genomförs."
            ),
            "questions": [
                "Lockar gestaltning, design och rumslig form mer än konstruktion, teknik och hur byggnader faktiskt realiseras?",
                "Vill du hellre arbeta med arkitektoniska idéer och användarupplevelse, eller med byggteknik, konstruktion och genomförande?",
            ],
        },
        {
            "terms": ["journalistik", "kommunikation"],
            "domain": "media_communication",
            "answer": (
                "De områdena ligger nära varandra men leder ofta till olika typer av roller. Journalistik brukar vara mer inriktat på nyhetsvärdering, granskning och berättande för allmänheten, "
                "medan kommunikation och PR oftare handlar om varumärken, budskap, relationer och strategisk påverkan i organisationer."
            ),
            "questions": [
                "Lockar granskning, nyhetsarbete och redaktionellt berättande mer än strategisk kommunikation och varumärkesarbete?",
                "Vill du hellre informera allmänheten oberoende, eller arbeta närmare organisationer, budskap och kommunikationsstrategi?",
            ],
        },
        {
            "terms": ["journalistik", "pr"],
            "domain": "media_communication",
            "answer": (
                "Det är två ganska olika riktningar trots att båda arbetar med innehåll och budskap. Journalistik går oftare mot granskning, nyheter och redaktionellt oberoende, "
                "medan PR handlar mer om att bygga relationer, forma budskap och företräda organisationer eller varumärken."
            ),
            "questions": [
                "Lockar redaktionellt och oberoende berättande mer än att arbeta för en organisation eller ett varumärke?",
                "Vill du hellre granska och rapportera, eller påverka hur en organisation kommunicerar utåt?",
            ],
        },
        {
            "terms": ["datavetenskap", "mjukvaruteknik"],
            "domain": "tech",
            "answer": (
                "Det är en relevant skillnad. Datavetenskap brukar ligga närmare de teoretiska grunderna i datorer, algoritmer och beräkning, "
                "medan mjukvaruteknik oftare är mer tillämpat mot hur större programvarusystem planeras, byggs, testas och underhålls."
            ),
            "questions": [
                "Lockar algoritmer, teori och datorernas grundprinciper mer än hur man utvecklar och förvaltar större programvarusystem?",
                "Vill du hellre gå mot datorvetenskaplig förståelse, eller mot ett mer praktiskt spår kring utvecklingsprocess, kvalitet och systembygge?",
            ],
        },
        {
            "terms": ["sjuksköterska", "läkare"],
            "domain": "healthcare",
            "answer": (
                "Det är två tydligt patientnära spår, men de skiljer sig mycket i ansvar, längd och vardag. Sjuksköterskespåret går snabbare mot patientarbete, omvårdnad och koordinering i vården, "
                "medan läkarspåret är längre och mer fokuserat på diagnostik, medicinska beslut och behandling."
            ),
            "questions": [
                "Lockar patientkontakt och omvårdnad i team mer än det längre medicinska ansvaret kring diagnos och behandling?",
                "Vill du snabbare ut i vårdyrket, eller kan du tänka dig en längre och mer krävande utbildningsväg för ett mer omfattande medicinskt ansvar?",
            ],
        },
        {
            "terms": ["marknadsföring", "ekonomi"],
            "domain": "business",
            "answer": (
                "Det valet handlar ofta om om du dras mer mot kommunikation och kundperspektiv eller mot analys och affärsbeslut. Marknadsföring ligger närmare varumärke, målgrupper och kommunikation, "
                "medan ekonomi oftare är bredare mot företag, finans, redovisning och analys."
            ),
            "questions": [
                "Lockar kommunikation, varumärke och kundinsikter mer än siffror, analys och ekonomiska beslut?",
                "Vill du hellre arbeta med hur företag når ut, eller med hur företag styrs och följs upp ekonomiskt?",
            ],
        },
        {
            "terms": ["bioteknik", "biomedicin"],
            "domain": "healthcare",
            "answer": (
                "De ligger nära biologiskt, men drar åt lite olika håll. Bioteknik brukar oftare kombinera biologi med teknik, processer och industriella tillämpningar, "
                "medan biomedicin oftare ligger närmare människokroppen, sjukdomsmekanismer och medicinsk forskning."
            ),
            "questions": [
                "Lockar teknik- och processdelen mer, eller är du mer intresserad av medicin, sjukdom och biologin bakom hälsa?",
                "Vill du hellre gå mot industriella tillämpningar och utveckling, eller mot forskning och medicinsk förståelse?",
            ],
        },
        {
            "terms": ["arkitekt", "samhällsplanerare"],
            "domain": "built_environment",
            "answer": (
                "Det är två närliggande men olika samhällsbyggnadsspår. Arkitekt går oftare närmare byggnader, gestaltning och rumslig design, "
                "medan samhällsplanering brukar vara bredare mot städer, markanvändning, infrastruktur och hur hela miljöer utvecklas."
            ),
            "questions": [
                "Vill du arbeta närmare enskilda byggnader och gestaltning, eller med hur stadsdelar och samhällen planeras i större skala?",
                "Lockar form och rum mer än policy, infrastruktur och långsiktig samhällsutveckling?",
            ],
        },
    ]
    LISTING_PATTERNS = [
        "vad finns det för utbildningar",
        "vilka utbildningar finns",
        "alla utbildningar i",
        "alla program i",
        "visa alla utbildningar i",
        "show all programs in",
        "utbildningar på distans",
        "program på distans",
        "hitta utbildningar på distans",
        "distans utbildningar",
        "distansutbildningar",
        "what programs are in",
        "what programmes are in",
        "show me programs in",
        "visa utbildningar i",
        "visa program i",
    ]

    GENERIC_CAREER_PHRASES = {
        "jag vill jobba",
        "jag vill arbeta",
        "intresserad av",
        "jobba med",
        "arbeta med",
        "vill jobba",
        "vill arbeta",
        "i am interested in",
        "i want to work",
        "jag gillar",
        "i like",
        "vill lära mig",
        "want to learn",
    }

    EXPLORATION_PHRASES = {
        "jag gillar",
        "i like",
        "jag är intresserad av",
        "i am interested in",
        "vill lära mig",
        "want to learn",
        "kombinera",
        "combine",
        "både",
        "both",
    }

    TOP_LEVEL_VAGUE_PATTERNS = {
        "jag vet inte vad jag vill plugga",
        "jag vet inte vad jag vill läsa",
        "jag vet inte vad jag ska plugga",
        "jag vet inte vad jag ska läsa",
        "visa mig något intressant",
        "visa mig nagot intressant",
        "ge mig något intressant",
        "ge mig nagot intressant",
        "visa något intressant",
        "visa nagot intressant",
        "något intressant",
        "nagot intressant",
    }

    MOTIVATION_KEYWORDS = {
        "people_oriented": {
            "jobba med människor",
            "arbeta med människor",
            "med människor",
            "hjälpa andra",
            "patientnära",
            "people",
            "help others",
        },
        "creative_career": {
            "kreativ",
            "skapande",
            "creative",
            "digital produktion",
            "jobbchanser",
            "job prospects",
        },
        "salary_focus": {
            "bra lön",
            "hög lön",
            "good salary",
            "high salary",
            "välbetalt",
            "jobb med bra lön",
        },
        "future_focus": {
            "framtidsmöjligheter",
            "framtidssäkert",
            "framtidssaker",
            "bra framtid",
            "trygg framtid",
            "god arbetsmarknad",
            "framtidsutsikter",
            "future prospects",
            "future opportunities",
            "good future opportunities",
        },
    }

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    @staticmethod
    def _count_matches(text: str, keywords) -> int:
        total = 0
        for keyword in keywords:
            pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
            if re.search(pattern, text):
                total += 1
        return total

    def _detect_domains(self, text: str, current_domains: Optional[List[str]]) -> Dict[str, Any]:
        scores = {
            domain: self._count_matches(text, keywords)
            for domain, keywords in DOMAIN_KEYWORDS.items()
        }
        ranked = sorted(
            [(domain, score) for domain, score in scores.items() if score > 0],
            key=lambda item: item[1],
            reverse=True,
        )
        if ranked:
            domains = [domain for domain, _ in ranked[:3]]
            confidence = min(0.95, 0.35 + 0.15 * ranked[0][1])
            return {
                "domain": domains[0],
                "domains": domains,
                "confidence": round(confidence, 2),
                "scores": scores,
            }

        if current_domains and len(text.split()) <= 8:
            return {
                "domain": current_domains[0],
                "domains": current_domains[:2],
                "confidence": 0.2,
                "scores": scores,
            }

        return {"domain": None, "domains": [], "confidence": 0.0, "scores": scores}

    def _detect_tracks(self, text: str, domains: List[str]) -> List[str]:
        if not domains:
            return []

        scored_tracks = []
        for domain in domains:
            for track, keywords in TRACK_KEYWORDS.get(domain, {}).items():
                score = self._count_matches(text, keywords)
                if score > 0:
                    scored_tracks.append((track, score))

        scored_tracks.sort(key=lambda item: item[1], reverse=True)
        deduped = []
        seen = set()
        for track, _ in scored_tracks:
            if track in seen:
                continue
            seen.add(track)
            deduped.append(track)
            if len(deduped) >= 4:
                break
        return deduped

    @staticmethod
    def _bridge_keys(domains: List[str]) -> List[tuple]:
        if len(domains) < 2:
            return []
        keys = []
        for i, left in enumerate(domains):
            for right in domains[i + 1 :]:
                key = tuple(sorted((left, right)))
                if key not in keys:
                    keys.append(key)
        return keys

    def _detect_bridge_paths(self, text: str, domains: List[str]) -> List[Dict[str, str]]:
        suggestions: List[Dict[str, str]] = []
        seen = set()
        explicit_music_signal = any(token in text for token in ["musik", "music", "ljud", "sound"])
        for key in self._bridge_keys(domains):
            if key == ("art", "tech") and "media_communication" in domains and not explicit_music_signal:
                continue
            paths = BRIDGE_PATHS.get(key, [])
            if key == ("humanities", "tech") and any(token in text for token in ["samhälle", "society", "policy", "democracy", "demokrati", "offentlig"]):
                paths = SOCIETY_TECH_BRIDGE_PATHS
            for path in paths:
                if path["id"] in seen:
                    continue
                seen.add(path["id"])
                suggestions.append(path)
        return suggestions[:4]

    def _detect_motivation_guidance(self, text: str) -> Optional[Dict[str, Any]]:
        for motivation, keywords in self.MOTIVATION_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                guidance = MOTIVATION_GUIDANCE[motivation]
                return {
                    "motivation_mode": motivation,
                    "clarification_answer": guidance["answer"],
                    "clarification_answer_en": guidance.get("answer_en", guidance["answer"]),
                    "clarification_options": guidance["options"],
                    "follow_up_questions": [option["label"] for option in guidance["options"]],
                    "follow_up_questions_en": [option.get("label_en", option["label"]) for option in guidance["options"]],
                    "needs_clarification": True,
                }
        return None

    def _detect_top_level_guidance(self, text: str) -> Optional[Dict[str, Any]]:
        if any(pattern in text for pattern in self.TOP_LEVEL_VAGUE_PATTERNS):
            return {
                "domain": None,
                "domains": [],
                "confidence": 0.2,
                "is_vague": False,
                "is_exploratory": False,
                "is_listing_query": False,
                "career_track_candidates": [],
                "bridge_path_suggestions": [],
                "needs_clarification": True,
                "clarification_answer": (
                    "Det är helt rimligt att börja brett. "
                    "I stället för att gissa direkt vill jag först ringa in vilket huvudområde som känns mest relevant för dig."
                ),
                "clarification_options": self.TOP_LEVEL_GUIDANCE_OPTIONS,
                "follow_up_questions": [option["label"] for option in self.TOP_LEVEL_GUIDANCE_OPTIONS[:4]],
            }
        return None

    def _detect_human_tech_path(self, text: str) -> Optional[Dict[str, Any]]:
        explicit_terms = [
            "interagerar med teknik",
            "interagera med teknik",
        ]
        psychology_terms = ["psykologi", "beteende", "människan", "manniskan", "människa", "manniska"]
        tech_terms = ["teknik", "digital", "interaktion", "interagerar", "system", "produkt"]
        design_terms: list = []

        has_explicit = any(term in text for term in explicit_terms)
        has_psychology_tech = any(term in text for term in psychology_terms) and any(term in text for term in tech_terms)
        has_design_psych_tech = "design" in text and any(term in text for term in psychology_terms) and any(term in text for term in tech_terms)
        if not (has_explicit or has_psychology_tech or has_design_psych_tech or (any(term in text for term in design_terms) and any(term in text for term in tech_terms))):
            return None

        bridge_path = next(
            (
                path
                for path in BRIDGE_PATHS.get(("psychology_social", "tech"), [])
                if path.get("id") == "behavioural_ux"
            ),
            None,
        )
        if not bridge_path:
            return None

        return {
            "domain": "tech",
            "domains": ["psychology_social", "tech"],
            "confidence": 0.88,
            "is_vague": False,
            "is_exploratory": True,
            "is_listing_query": False,
            "career_track_candidates": ["ux_hci"],
            "bridge_path_suggestions": [bridge_path],
            "follow_up_questions": [bridge_path["question"], *bridge_path.get("next_questions", [])][:3],
        }

    def _is_exploratory(
        self,
        text: str,
        domains: List[str],
        tracks: List[str],
        bridge_paths: List[Dict[str, str]],
    ) -> bool:
        if len(domains) >= 2:
            return True
        if bridge_paths:
            return True
        if any(phrase in text for phrase in self.EXPLORATION_PHRASES) and len(tracks) <= 1:
            return True
        return False

    @staticmethod
    def _mentions_city(text: str) -> bool:
        """Return True if the text mentions a known Swedish city."""
        tokens = set(re.split(r"[\s,]+", text.lower()))
        return bool(tokens & set(CITY_ALIASES.keys()))

    def _is_vague(self, text: str, domain: Optional[str], tracks: List[str]) -> bool:
        if not domain:
            return False

        has_generic_career_signal = any(phrase in text for phrase in self.GENERIC_CAREER_PHRASES)
        has_specific_role_signal = any(term in text for term in DOMAIN_SPECIFIC_ROLE_TERMS.get(domain, set()))
        short_prompt = len(text.split()) <= 10

        if domain == "healthcare" and "patientnära" in text and not has_specific_role_signal:
            return True

        if has_generic_career_signal and not has_specific_role_signal:
            return True

        # A short prompt with no specific role signal is vague — unless the user
        # has already specified a city, which means they have enough context for
        # recommendations (e.g. "IT i Göteborg" should go straight to results).
        if short_prompt and not tracks and not has_specific_role_signal:
            if self._mentions_city(text):
                return False
            return True

        return False

    def analyze(
        self,
        message: str,
        profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        profile = profile or {}
        text = self._normalize(message)
        current_domains = profile.get("current_domains") or ([profile["current_domain"]] if profile.get("current_domain") else [])
        motivation_hint = self._detect_motivation_guidance(text)

        for comparison in self.COMPARISON_PATTERNS:
            if all(term in text for term in comparison["terms"]):
                return {
                    "domain": comparison["domain"],
                    "domains": [comparison["domain"]],
                    "confidence": 0.9,
                    "is_vague": False,
                    "is_exploratory": False,
                    "is_listing_query": False,
                    "is_comparison_query": True,
                    "comparison_answer": comparison["answer"],
                    "follow_up_questions": comparison["questions"],
                    "career_track_candidates": [],
                    "bridge_path_suggestions": [],
                }

        human_tech_path = self._detect_human_tech_path(text)
        if human_tech_path:
            return human_tech_path

        top_level_guidance = self._detect_top_level_guidance(text)
        if top_level_guidance:
            return top_level_guidance

        domain_result = self._detect_domains(text, [] if motivation_hint else current_domains)
        domain = domain_result["domain"]
        domains = domain_result.get("domains", [])
        tracks = self._detect_tracks(text, domains)
        bridge_paths = self._detect_bridge_paths(text, domains)
        is_exploratory = self._is_exploratory(text, domains, tracks, bridge_paths)
        is_vague = self._is_vague(text, domain, tracks)
        motivation_guidance = None
        if not bridge_paths and len(domains) < 2:
            motivation_guidance = motivation_hint
        is_listing_query = any(pattern in text for pattern in self.LISTING_PATTERNS)

        follow_up_questions = []
        if motivation_guidance:
            follow_up_questions.extend(motivation_guidance["follow_up_questions"])
        elif bridge_paths:
            follow_up_questions.extend(path["question"] for path in bridge_paths[:3])
        elif is_exploratory and domain:
            follow_up_questions.extend(DOMAIN_FOLLOW_UP_QUESTIONS.get(domain, [])[:3])
        else:
            follow_up_questions.extend(DOMAIN_FOLLOW_UP_QUESTIONS.get(domain or "other", [])[:3])

        # Collect role terms from the message that directly match domain-specific vocabulary.
        # Used downstream to populate career_goals for better explanation quality.
        matched_role_terms: List[str] = []
        for d in (domains or ([domain] if domain else [])):
            for term in DOMAIN_SPECIFIC_ROLE_TERMS.get(d, set()):
                if term in text:
                    matched_role_terms.append(term)

        result = {
            "domain": domain,
            "domains": domains,
            "confidence": domain_result["confidence"],
            "is_vague": is_vague,
            "is_exploratory": is_exploratory,
            "is_listing_query": is_listing_query,
            "career_track_candidates": tracks,
            "bridge_path_suggestions": bridge_paths,
            "follow_up_questions": follow_up_questions[:3],
            "matched_role_terms": matched_role_terms[:3],
        }
        if motivation_guidance:
            result.update(motivation_guidance)
        return result
