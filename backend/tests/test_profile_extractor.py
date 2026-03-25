from app.services.profile_extractor import ProfileExtractor


def test_extracts_mittuniversitetet_as_preferred_university():
    extracted = ProfileExtractor.extract(
        "Lista alla utbildningar som är kandidat på Mittuniversitetet"
    )

    assert extracted["preferred_universities"] == ["Mittuniversitetet"]


def test_extracts_chalmers_and_excludes_goteborgs_universitet():
    extracted = ProfileExtractor.extract(
        "Jag vill plugga IT på Chalmers i Göteborg, inte Göteborgs universitet"
    )

    assert extracted["preferred_universities"] == ["Chalmers tekniska högskola"]
    assert extracted["excluded_universities"] == ["Göteborgs universitet"]
