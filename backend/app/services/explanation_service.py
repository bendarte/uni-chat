from typing import Any, Dict, List

from app.services.source_validation import is_valid_source_url, normalize_source_url


class ExplanationService:
    TRACK_EXPLANATIONS = {
        "ai_data": "Det här ligger nära spåret AI och data som du verkar vara ute efter.",
        "business_analytics": "Det här ligger nära spåret business analytics med fokus på analys, data och affärsbeslut.",
        "product_management": "Det här ligger nära spåret produktledning i teknikbolag med fokus på affär, digital utveckling och förändring.",
        "health_tech": "Det här ligger nära spåret health tech där vård möter teknik och digital utveckling.",
        "digital_media_communication": "Det här ligger nära spåret digital media och kommunikation där innehåll möter teknik.",
        "energy_transition": "Det här ligger nära spåret energi, hållbarhet och omställning som du verkar vara ute efter.",
    }

    @staticmethod
    def _variant_seed(program: Dict[str, Any], salt: str = "") -> int:
        basis = "||".join(
            [
                salt,
                str(program.get("program_id") or ""),
                str(program.get("name") or ""),
                str(program.get("field") or ""),
                str(program.get("university") or ""),
            ]
        )
        return sum((index + 1) * ord(ch) for index, ch in enumerate(basis))

    @classmethod
    def _pick_variant(cls, program: Dict[str, Any], options: List[str], salt: str = "") -> str:
        if not options:
            return ""
        return options[cls._variant_seed(program, salt=salt) % len(options)]

    @staticmethod
    def _display_city(city: Any) -> str:
        value = str(city or "").strip()
        if value == "Online":
            return "distans"
        return value

    @staticmethod
    def _display_level(level: Any) -> str:
        value = str(level or "").strip().lower()
        if value == "master":
            return "masternivå"
        if value == "bachelor":
            return "kandidatnivå"
        if value == "phd":
            return "forskarutbildning"
        return value

    @staticmethod
    def _display_language(language: Any) -> str:
        value = str(language or "").strip().lower()
        if value == "english":
            return "engelska"
        if value == "swedish":
            return "svenska"
        return value

    @staticmethod
    def _display_study_pace(study_pace: Any) -> str:
        value = str(study_pace or "").strip().lower()
        if value == "full-time":
            return "heltid"
        if value == "part-time":
            return "deltid"
        return value

    @staticmethod
    def _clean_terms(values: Any) -> List[str]:
        terms: List[str] = []
        seen = set()
        for value in values or []:
            clean = str(value or "").strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            terms.append(clean)
        return terms

    @classmethod
    def _interest_match(cls, user_profile: Dict[str, Any], program: Dict[str, Any]) -> str:
        interests = cls._clean_terms(user_profile.get("interests", []))
        if not interests:
            return ""

        haystack = " ".join(
            [
                str(program.get("name") or ""),
                str(program.get("field") or ""),
                str(program.get("description") or ""),
                str(program.get("career_paths") or ""),
            ]
        ).lower()

        matched = [interest for interest in interests if interest.lower() in haystack][:2]
        if matched:
            if len(matched) == 1:
                return cls._pick_variant(
                    program,
                    [
                        f"Det här ligger nära det du frågade om inom {matched[0]}.",
                        f"Om {matched[0]} är viktigt för dig är det här en relevant träff.",
                        f"Jag tog med det här eftersom innehållet ligger nära {matched[0]}.",
                    ],
                    salt="interest-single",
                )
            return cls._pick_variant(
                program,
                [
                    f"Det här ligger nära det du frågade om inom {matched[0]} och {matched[1]}.",
                    f"Jag tog med det här eftersom programmet fångar både {matched[0]} och {matched[1]}.",
                    f"Det här ser relevant ut om du vill kombinera {matched[0]} och {matched[1]}.",
                ],
                salt="interest-double",
            )

        return ""

    @classmethod
    def _goal_match(cls, user_profile: Dict[str, Any], program: Dict[str, Any]) -> str:
        goals = cls._clean_terms(user_profile.get("career_goals", []))
        career_paths = str(program.get("career_paths") or "").strip()
        if not goals or not career_paths:
            return ""

        haystack = career_paths.lower()
        matched = [goal for goal in goals if goal.lower() in haystack][:1]
        if matched:
            return cls._pick_variant(
                program,
                [
                    f"I källan nämns karriärspår som ligger nära ditt mål att arbeta som {matched[0]}.",
                    f"Det här känns extra relevant eftersom källan pekar mot roller nära {matched[0]}.",
                    f"Jag tog med det här eftersom källan nämner yrkesvägar som ligger nära {matched[0]}.",
                ],
                salt="goal",
            )
        return ""

    @classmethod
    def _guidance_match(cls, user_profile: Dict[str, Any], program: Dict[str, Any]) -> str:
        option = user_profile.get("selected_guidance_option") or {}
        option_label = str(option.get("label") or "").strip()
        if option_label:
            return cls._pick_variant(
                program,
                [
                    f"Det här ligger nära spåret {option_label.lower()} som du nyss valde.",
                    f"Om du vill gå mot {option_label.lower()} är det här ett rimligt nästa steg att titta på.",
                    f"Det här passar ganska väl med riktningen {option_label.lower()} som du valde nyss.",
                ],
                salt="guidance",
            )

        current_tracks = [
            str(track).strip().lower()
            for track in (user_profile.get("current_tracks") or [])
            if str(track).strip()
        ]
        program_tracks = {
            str(track).strip().lower()
            for track in (program.get("tracks") or [])
            if str(track).strip()
        }
        for track in current_tracks:
            if track in program_tracks and track in cls.TRACK_EXPLANATIONS:
                return cls.TRACK_EXPLANATIONS[track]
            if track == "energy_transition":
                focus_text = " ".join(
                    [
                        str(program.get("name") or ""),
                        str(program.get("field") or ""),
                        str(program.get("description") or ""),
                    ]
                ).lower()
                if any(marker in focus_text for marker in ["energy", "energi", "sustainable", "hållbar", "environment", "miljö"]):
                    return cls.TRACK_EXPLANATIONS[track]
        return ""

    @classmethod
    def _preference_match(cls, user_profile: Dict[str, Any], program: Dict[str, Any]) -> List[str]:
        bullets: List[str] = []

        preferred_cities = cls._clean_terms(user_profile.get("preferred_cities", []))
        if preferred_cities:
            city = str(program.get("city") or "").strip()
            if city and city.lower() in {value.lower() for value in preferred_cities}:
                city_label = cls._display_city(city)
                if city_label == "distans":
                    bullets.append(
                        cls._pick_variant(
                            program,
                            [
                                "Det här ges på distans, vilket passar ditt val.",
                                "Om flexibilitet är viktigt för dig är det här en tydlig distansträff.",
                                "Platsen stämmer också: det här läses på distans.",
                            ],
                            salt="city-distance",
                        )
                    )
                else:
                    bullets.append(
                        cls._pick_variant(
                            program,
                            [
                                f"Det här ges i {city_label}, vilket stämmer med staden du valde.",
                                f"Platsen matchar också: programmet ges i {city_label}.",
                                f"Om {city_label} är viktigt för dig är det här en tydlig platsmatch.",
                            ],
                            salt="city",
                        )
                    )

        preferred_level = str(user_profile.get("study_level") or "").strip().lower()
        level = str(program.get("level") or "").strip().lower()
        if preferred_level and level and preferred_level == level:
            level_label = cls._display_level(level)
            bullets.append(
                cls._pick_variant(
                    program,
                    [
                        f"Nivån stämmer också: det här är ett program på {level_label}.",
                        f"Det här ligger på {level_label}, vilket passar det du bad om.",
                        f"Bra att veta: programmet ges på {level_label}, så nivåvalet matchar.",
                    ],
                    salt="level",
                )
            )

        preferred_language = str(user_profile.get("language") or "").strip().lower()
        language = str(program.get("language") or "").strip().lower()
        if preferred_language and language and preferred_language == language:
            language_label = cls._display_language(language)
            bullets.append(
                cls._pick_variant(
                    program,
                    [
                        f"Undervisningen är på {language_label}, vilket passar ditt språkval.",
                        f"Språket matchar också: programmet ges på {language_label}.",
                        f"Det här är ett rimligt val om du vill läsa på {language_label}.",
                    ],
                    salt="language",
                )
            )

        preferred_study_pace = str(user_profile.get("study_pace") or "").strip().lower()
        study_pace = str(program.get("study_pace") or "").strip().lower()
        if preferred_study_pace and study_pace and preferred_study_pace == study_pace:
            study_pace_label = cls._display_study_pace(study_pace)
            bullets.append(
                cls._pick_variant(
                    program,
                    [
                        f"Studietakten är {study_pace_label}, vilket passar ditt upplägg.",
                        f"Upplägget stämmer också: det här läses på {study_pace_label}.",
                        f"Det här matchar även din önskade takt, eftersom programmet ges på {study_pace_label}.",
                    ],
                    salt="pace",
                )
            )

        return bullets

    @classmethod
    def _program_summary(cls, program: Dict[str, Any]) -> str:
        field = str(program.get("field") or "").strip()
        if field.lower() in {"general", "other"}:
            return cls._pick_variant(
                program,
                [
                    "Det här ser ut som ett bredare program snarare än en väldigt smal specialisering.",
                    "Utbildningen verkar ha en bredare profil snarare än en snäv nisch.",
                    "Det här framstår som ett ganska brett program med flera möjliga vägar vidare.",
                ],
                salt="summary-broad",
            )
        if field:
            return cls._pick_variant(
                program,
                [
                    f"Tyngdpunkten här ligger på {field}.",
                    f"Huvudspåret i programmet är {field}.",
                    f"Innehållet kretsar framför allt kring {field}.",
                ],
                salt="summary-field",
            )

        description = " ".join(str(program.get("description") or "").split())
        if description:
            short = description[:180].rstrip()
            if len(description) > 180:
                short += "..."
            return short

        return cls._pick_variant(
            program,
            [
                "Programmet har en tydlig utbildningsprofil enligt källan.",
                "Källan beskriver ett ganska tydligt utbildningsupplägg här.",
                "Det här framstår som ett program med en tydlig inriktning enligt källan.",
            ],
            salt="summary-generic",
        )

    @classmethod
    def _career_summary(cls, program: Dict[str, Any]) -> str:
        career_paths = " ".join(str(program.get("career_paths") or "").split())
        if career_paths:
            if len(career_paths) > 180:
                career_paths = career_paths[:177].rstrip() + "..."
            return cls._pick_variant(
                program,
                [
                    f"Källan beskriver möjliga spår som {career_paths}.",
                    f"Enligt källan kan utbildningen leda vidare mot spår som {career_paths}.",
                    f"I källmaterialet nämns fortsatta yrkesvägar som {career_paths}.",
                ],
                salt="career",
            )
        return cls._pick_variant(
            program,
            [
                "Källan specificerar inte tydliga karriärspår, så här får du främst gå på innehåll och upplägg.",
                "Källan är inte helt tydlig om yrkesvägarna, så här är det klokast att bedöma innehåll och form.",
                "Här behöver du främst gå på själva innehållet i programmet, eftersom källan säger mindre om konkreta karriärspår.",
            ],
            salt="career-generic",
        )

    @classmethod
    def _build_bullets(cls, user_profile: Dict[str, Any], program: Dict[str, Any]) -> List[str]:
        bullets: List[str] = []

        interest_match = cls._interest_match(user_profile, program)
        if interest_match:
            bullets.append(interest_match)

        guidance_match = cls._guidance_match(user_profile, program)
        if guidance_match:
            bullets.append(guidance_match)

        bullets.extend(cls._preference_match(user_profile, program))

        goal_match = cls._goal_match(user_profile, program)
        if goal_match:
            bullets.append(goal_match)

        if len(bullets) < 2:
            bullets.append(cls._program_summary(program))
        if len(bullets) < 3:
            bullets.append(cls._career_summary(program))

        deduped: List[str] = []
        seen = set()
        for bullet in bullets:
            clean = str(bullet or "").strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(clean)
            if len(deduped) >= 3:
                break

        while len(deduped) < 3:
            deduped.append(
                cls._pick_variant(
                    program,
                    [
                        "Det här ser ut som ett relevant program utifrån innehåll, upplägg och tillgänglig källinformation.",
                        "Sammantaget är det här en rimlig träff utifrån det som går att läsa ut av källan.",
                        "På helheten är det här ett program som ligger nära det du verkar söka.",
                    ],
                    salt="fallback",
                )
            )

        return deduped

    def generate_program_explanation(
        self,
        user_profile: Dict[str, Any],
        program: Dict[str, Any],
    ) -> Dict[str, Any]:
        source_url = normalize_source_url(program.get("source_url"))
        if not is_valid_source_url(source_url):
            source_url = ""

        return {
            "program_id": str(program.get("program_id", "")),
            "source_id": f"ref-{str(program.get('program_id', 'unknown'))[:8]}",
            "program": str(program.get("name") or ""),
            "university": str(program.get("university") or ""),
            "explanation": self._build_bullets(user_profile, program),
        }
