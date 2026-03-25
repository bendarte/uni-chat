from ingestion.crawl_study_programs import parse_api_item
from ingestion.parse_programs import to_db_record


def test_parse_api_item_normalizes_university_aliases():
    record = parse_api_item(
        {
            "anmalningsalternativ": {
                "kursbeskrivningUrl": "https://www.universityadmissions.se/intl/study/programme/example",
                "titel": "Computer science - algorithms, languages and logic (master's programme)",
                "organisation": "Chalmers University of Technology",
                "studieort": "Gothenburg",
                "utbildningsniva": "Master's level",
                "undervisningssprak": "English",
                "valdaAmnesNamn": ["Computer Science"],
                "studietakt": "100",
            }
        },
        source="universityadmissions.se",
        default_language="English",
    )

    assert record is not None
    assert record["university"] == "Chalmers tekniska högskola"


def test_to_db_record_normalizes_university_aliases():
    record = to_db_record(
        {
            "name": "Computer science - algorithms, languages and logic (master's programme)",
            "university": "Chalmers University of Technology",
            "source_url": "https://www.universityadmissions.se/intl/study/programme/example",
            "city": "Gothenburg",
            "country": "Sweden",
            "level": "master",
            "language": "English",
        }
    )

    assert record is not None
    assert record["university"] == "Chalmers tekniska högskola"
