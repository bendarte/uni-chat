#!/usr/bin/env python3
"""Insert high-demand missing programs into the university_ai database."""

import subprocess
import uuid


def build_id(source_url: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, source_url.lower()))


# Each tuple:
# (name, university, city, country, level, language, study_pace, field,
#  description, career_paths, source_url, duration_years)
programs = [
    # --- Stockholm - Healthcare ---
    (
        "Sjuksköterskeprogrammet",
        "Karolinska Institutet",
        "Stockholm",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "health sciences",
        "Sjuksköterskeprogrammet at Karolinska Institutet. Level: Grundnivå. Subject areas: Omvårdnad. Pace: 100% Normal. Teaching time: Dagtid.",
        "Sjuksköterska, distriktssköterska, specialistsjuksköterska, vård och omsorg",
        "https://ki.se/utbildning/sjukskoterskeprogrammet",
        3,
    ),
    (
        "Läkarprogrammet",
        "Karolinska Institutet",
        "Stockholm",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "health sciences",
        "Läkarprogrammet at Karolinska Institutet. Level: Grundnivå. Subject areas: Medicin. Pace: 100% Normal. Teaching time: Dagtid.",
        "Läkare, specialist, klinisk forskning",
        "https://ki.se/utbildning/lakarprogrammet",
        6,
    ),
    (
        "Psykologprogrammet",
        "Stockholms Universitet",
        "Stockholm",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "social sciences",
        "Psykologprogrammet at Stockholms Universitet. Level: Grundnivå. Subject areas: Psykologi. Pace: 100% Normal. Teaching time: Dagtid.",
        "Psykolog, terapeut, klinisk psykologi",
        "https://www.su.se/utbildning/psykologprogrammet",
        5,
    ),
    (
        "Socionomprogrammet",
        "Stockholms Universitet",
        "Stockholm",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "social sciences",
        "Socionomprogrammet at Stockholms Universitet. Level: Grundnivå. Subject areas: Socialt arbete. Pace: 100% Normal. Teaching time: Dagtid.",
        "Socionom, socialsekreterare, kurator, familjerådgivare",
        "https://www.su.se/utbildning/socionomprogrammet",
        3,
    ),
    (
        "Juristprogrammet",
        "Stockholms Universitet",
        "Stockholm",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "social sciences",
        "Juristprogrammet at Stockholms Universitet. Level: Grundnivå. Subject areas: Juridik. Pace: 100% Normal. Teaching time: Dagtid.",
        "Jurist, advokat, domare, åklagare",
        "https://www.su.se/utbildning/juristprogrammet",
        4,
    ),
    (
        "Kandidatprogrammet i ekonomi",
        "Stockholms Universitet",
        "Stockholm",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "business",
        "Kandidatprogrammet i ekonomi at Stockholms Universitet. Level: Grundnivå. Subject areas: Nationalekonomi. Pace: 100% Normal. Teaching time: Dagtid.",
        "Ekonom, analytiker, redovisningskonsult, revisor",
        "https://www.su.se/utbildning/kandidatprogrammet-i-economics",
        3,
    ),
    # --- Stockholm - Tech ---
    (
        "Civilingenjör Datateknik",
        "KTH",
        "Stockholm",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "computer science",
        "Civilingenjör Datateknik at KTH. Level: Grundnivå. Subject areas: Datateknik. Pace: 100% Normal. Teaching time: Dagtid.",
        "Mjukvaruutvecklare, systemutvecklare, IT-konsult, teknisk specialist",
        "https://www.kth.se/utbildning/civilingenjor/datateknik",
        5,
    ),
    # --- Gothenburg - Healthcare ---
    (
        "Sjuksköterskeprogrammet",
        "Göteborgs Universitet",
        "Gothenburg",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "health sciences",
        "Sjuksköterskeprogrammet at Göteborgs Universitet. Level: Grundnivå. Subject areas: Omvårdnad. Pace: 100% Normal. Teaching time: Dagtid.",
        "Sjuksköterska, distriktssköterska, specialistsjuksköterska, vård och omsorg",
        "https://www.gu.se/utbildning/sjukskoterskeprogrammet",
        3,
    ),
    (
        "Läkarprogrammet",
        "Göteborgs Universitet",
        "Gothenburg",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "health sciences",
        "Läkarprogrammet at Göteborgs Universitet. Level: Grundnivå. Subject areas: Medicin. Pace: 100% Normal. Teaching time: Dagtid.",
        "Läkare, specialist, klinisk forskning",
        "https://www.gu.se/utbildning/lakarprogrammet",
        6,
    ),
    (
        "Psykologprogrammet",
        "Göteborgs Universitet",
        "Gothenburg",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "social sciences",
        "Psykologprogrammet at Göteborgs Universitet. Level: Grundnivå. Subject areas: Psykologi. Pace: 100% Normal. Teaching time: Dagtid.",
        "Psykolog, terapeut, klinisk psykologi",
        "https://www.gu.se/utbildning/psykologprogrammet",
        5,
    ),
    # --- Gothenburg - Tech ---
    (
        "Civilingenjör Datateknik",
        "Chalmers tekniska högskola",
        "Gothenburg",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "computer science",
        "Civilingenjör Datateknik at Chalmers tekniska högskola. Level: Grundnivå. Subject areas: Datateknik. Pace: 100% Normal. Teaching time: Dagtid.",
        "Mjukvaruutvecklare, systemutvecklare, IT-konsult, teknisk specialist",
        "https://www.chalmers.se/utbildning/civilingenjor-datateknik",
        5,
    ),
    (
        "Civilingenjör Informationsteknik",
        "Chalmers tekniska högskola",
        "Gothenburg",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "computer science",
        "Civilingenjör Informationsteknik at Chalmers tekniska högskola. Level: Grundnivå. Subject areas: Informationsteknik. Pace: 100% Normal. Teaching time: Dagtid.",
        "Mjukvaruutvecklare, systemutvecklare, IT-konsult, teknisk specialist",
        "https://www.chalmers.se/utbildning/civilingenjor-informationsteknik",
        5,
    ),
    # --- Lund ---
    (
        "Sjuksköterskeprogrammet",
        "Lunds Universitet",
        "Lund",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "health sciences",
        "Sjuksköterskeprogrammet at Lunds Universitet. Level: Grundnivå. Subject areas: Omvårdnad. Pace: 100% Normal. Teaching time: Dagtid.",
        "Sjuksköterska, distriktssköterska, specialistsjuksköterska, vård och omsorg",
        "https://www.lu.se/utbildning/sjukskoterskeprogrammet",
        3,
    ),
    (
        "Läkarprogrammet",
        "Lunds Universitet",
        "Lund",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "health sciences",
        "Läkarprogrammet at Lunds Universitet. Level: Grundnivå. Subject areas: Medicin. Pace: 100% Normal. Teaching time: Dagtid.",
        "Läkare, specialist, klinisk forskning",
        "https://www.lu.se/utbildning/lakarprogrammet",
        6,
    ),
    (
        "Juristprogrammet",
        "Lunds Universitet",
        "Lund",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "social sciences",
        "Juristprogrammet at Lunds Universitet. Level: Grundnivå. Subject areas: Juridik. Pace: 100% Normal. Teaching time: Dagtid.",
        "Jurist, advokat, domare, åklagare",
        "https://www.lu.se/utbildning/juristprogrammet",
        4,
    ),
    (
        "Psykologprogrammet",
        "Lunds Universitet",
        "Lund",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "social sciences",
        "Psykologprogrammet at Lunds Universitet. Level: Grundnivå. Subject areas: Psykologi. Pace: 100% Normal. Teaching time: Dagtid.",
        "Psykolog, terapeut, klinisk psykologi",
        "https://www.lu.se/utbildning/psykologprogrammet",
        5,
    ),
    (
        "Civilingenjör Datateknik",
        "Lunds Tekniska Högskola",
        "Lund",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "computer science",
        "Civilingenjör Datateknik at Lunds Tekniska Högskola. Level: Grundnivå. Subject areas: Datateknik. Pace: 100% Normal. Teaching time: Dagtid.",
        "Mjukvaruutvecklare, systemutvecklare, IT-konsult, teknisk specialist",
        "https://www.lth.se/utbildning/civilingenjor-datateknik",
        5,
    ),
    # --- Uppsala ---
    (
        "Sjuksköterskeprogrammet",
        "Uppsala Universitet",
        "Uppsala",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "health sciences",
        "Sjuksköterskeprogrammet at Uppsala Universitet. Level: Grundnivå. Subject areas: Omvårdnad. Pace: 100% Normal. Teaching time: Dagtid.",
        "Sjuksköterska, distriktssköterska, specialistsjuksköterska, vård och omsorg",
        "https://www.uu.se/utbildning/sjukskoterskeprogrammet",
        3,
    ),
    (
        "Läkarprogrammet",
        "Uppsala Universitet",
        "Uppsala",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "health sciences",
        "Läkarprogrammet at Uppsala Universitet. Level: Grundnivå. Subject areas: Medicin. Pace: 100% Normal. Teaching time: Dagtid.",
        "Läkare, specialist, klinisk forskning",
        "https://www.uu.se/utbildning/lakarprogrammet",
        6,
    ),
    (
        "Juristprogrammet",
        "Uppsala Universitet",
        "Uppsala",
        "Sweden",
        "bachelor",
        "Swedish",
        "full-time",
        "social sciences",
        "Juristprogrammet at Uppsala Universitet. Level: Grundnivå. Subject areas: Juridik. Pace: 100% Normal. Teaching time: Dagtid.",
        "Jurist, advokat, domare, åklagare",
        "https://www.uu.se/utbildning/juristprogrammet",
        4,
    ),
]

inserted = 0
skipped = 0
errors = 0

for prog in programs:
    (
        name, university, city, country, level, language, study_pace, field,
        description, career_paths, source_url, duration_years,
    ) = prog
    prog_id = build_id(source_url)

    sql = (
        "INSERT INTO programs "
        "(id, name, university, city, country, level, language, study_pace, field, "
        "description, career_paths, source_url, duration_years) "
        f"VALUES ('{prog_id}', $n${name}$n$, $u${university}$u$, '{city}', '{country}', "
        f"'{level}', '{language}', '{study_pace}', '{field}', "
        f"$d${description}$d$, $cp${career_paths}$cp$, '{source_url}', {duration_years}) "
        "ON CONFLICT (id) DO NOTHING;"
    )
    result = subprocess.run(
        ["docker", "exec", "uni_postgres", "psql", "-U", "postgres", "-d", "university_ai", "-c", sql],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR inserting {name} @ {university}: {result.stderr.strip()}")
        errors += 1
    elif "INSERT 0 0" in result.stdout:
        print(f"SKIPPED (already exists): {name} @ {university}")
        skipped += 1
    else:
        print(f"INSERTED: {name} @ {university}")
        inserted += 1

print(f"\nDone. Inserted: {inserted}, Skipped: {skipped}, Errors: {errors}")

# Verify total count
result = subprocess.run(
    ["docker", "exec", "uni_postgres", "psql", "-U", "postgres", "-d", "university_ai",
     "-c", "SELECT COUNT(*) FROM programs;"],
    capture_output=True,
    text=True,
)
print("\nTotal programs in DB:")
print(result.stdout.strip())
