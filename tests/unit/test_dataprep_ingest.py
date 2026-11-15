"""Fixtures below are hand-written to LOOK like scraped job CSVs. They are not the Kaggle files."""
import csv
import json
import zipfile

import pytest

from dataprep.clean import ascii_ratio, clean_text, looks_english, norm_key, parse_money, redact_contacts
from dataprep.ingest import SkillExtractor, detect_mapping, ingest, load_mapping, read_rows

ROWS = [
    {"Title": "Python ML engineer for churn model", "Description": "<p>We need a <b>Python</b> developer with scikit-learn &amp; pandas to build a churn model.&nbsp;Report precision and recall.</p>",
     "Published_Date": "2024-03-01", "Is_Hourly": "False", "Hourly_Low": "", "Hourly_High": "", "Budget": "$1,200", "Country": "US"},
    {"Title": "Python ML engineer for churn model", "Description": "We need a python developer with scikit-learn and pandas to build a churn model. Report precision and recall!",
     "Published_Date": "2024-03-02", "Is_Hourly": "False", "Hourly_Low": "", "Hourly_High": "", "Budget": "1200", "Country": "US"},       # near-duplicate
    {"Title": "React dashboard", "Description": "Short.", "Published_Date": "", "Is_Hourly": "", "Hourly_Low": "", "Hourly_High": "", "Budget": "", "Country": ""},   # too short
    {"Title": "Next.js and TypeScript developer", "Description": "Build a Next.js storefront in TypeScript with a PostgreSQL backend and REST API integration for our shop.",
     "Published_Date": "2024-04-01", "Is_Hourly": "True", "Hourly_Low": "25", "Hourly_High": "40", "Budget": "", "Country": "UK"},
    {"Title": "Traductor de contenido", "Description": "Necesitamos traducir documentos técnicos del inglés al español con urgencia, experiencia en traducción médica requerida.",
     "Published_Date": "", "Is_Hourly": "", "Hourly_Low": "", "Hourly_High": "", "Budget": "50", "Country": "ES"},                      # not english (ascii ratio)
    {"Title": "Data entry", "Description": "Enter product listings into a spreadsheet each day, accuracy matters and we pay on time every week without delay.",
     "Published_Date": "", "Is_Hourly": "", "Hourly_Low": "", "Hourly_High": "", "Budget": "", "Country": "IN"},                          # no budget: kept
]


@pytest.fixture
def csv_path(tmp_path):
    p = tmp_path / "jobs.csv"
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ROWS[0]))
        w.writeheader()
        w.writerows(ROWS)
    return p


def test_cleaning_primitives():
    assert clean_text("<p>Hi&nbsp;<b>there</b> &amp; you</p>") == "Hi there & you"
    assert parse_money("$1,200.50") == 1200.5 and parse_money("") is None and parse_money("abc") is None and parse_money(0) is None
    assert norm_key("A  B", "same text") == norm_key("a b", "Same, text!")
    assert ascii_ratio("hello") == 1.0 and ascii_ratio("¿qué?") < 1.0
    assert looks_english("We are looking for a developer with experience in the field") and not looks_english("Necesitamos traducir documentos técnicos del inglés al español")


def test_redact_contacts_preserves_dates_and_amounts():
    text = redact_contacts("Email dev@example.com or call +1 555 010 1234. Deadline 2026-11-12; budget $1,200.")
    assert "[email]" in text and "[phone]" in text
    assert "dev@example.com" not in text and "1234" not in text
    assert "2026-11-12" in text and "$1,200" in text


def test_mapping_is_detected_case_insensitively_and_fails_loudly_when_unmappable(tmp_path):
    assert detect_mapping(["Title", "Description", "Hourly_Low"], load_mapping())["hourly_low"] == "Hourly_Low"
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n")
    with pytest.raises(SystemExit, match="cannot map"):
        ingest([bad])


def test_ingest_cleans_dedupes_filters_and_labels_provenance(csv_path):
    jobs, stats = ingest([csv_path])
    assert stats["read"] == 6 and stats["kept"] == 3
    assert stats["dropped_duplicate"] == 1 and stats["dropped_too_short_or_untitled"] == 1 and stats["dropped_non_english"] == 1
    by = {j["title"]: j for j in jobs}
    churn = by["Python ML engineer for churn model"]
    assert churn["budget"] == {"min": 1200.0, "max": 1200.0, "currency": "USD", "unit": "project"}
    assert {"Python", "scikit-learn", "pandas"} <= set(churn["required_skills"]) and churn["category"] == "ml_ai"
    assert "<" not in churn["description"] and "&amp;" not in churn["description"]
    web = by["Next.js and TypeScript developer"]
    assert web["budget"]["unit"] == "hour" and (web["budget"]["min"], web["budget"]["max"]) == (25.0, 40.0)
    assert {"Next.js", "TypeScript", "SQL", "REST API"} <= set(web["required_skills"])
    assert by["Data entry"]["budget"]["max"] == 0                    # unknown budget is kept, not invented
    assert all(j["provenance"] == "real" and "client_id" in j["synthetic_fields"] for j in jobs)


def test_ingest_reads_single_csv_from_kaggle_zip(csv_path, tmp_path):
    archive_path = tmp_path / "upwork-jobs.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(csv_path, "upwork-jobs.csv")

    jobs, stats = ingest([archive_path])

    assert stats["read"] == 6 and stats["kept"] == 3
    assert {job["source_dataset"] for job in jobs} == {archive_path.name}


def test_zip_with_multiple_csv_files_fails_explicitly(tmp_path):
    archive_path = tmp_path / "ambiguous.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("a.csv", "title,description\n")
        archive.writestr("b.csv", "title,description\n")
    with pytest.raises(ValueError, match="expected exactly one CSV"):
        list(read_rows(archive_path))


def test_skill_extractor_word_boundaries():
    ex = SkillExtractor()
    assert ex.extract("We use JavaScript daily") == ["JavaScript"]            # no partial match inside the word
    assert "JavaScript" in ex.extract("We use JavaScript daily")
    assert "RAG" not in ex.extract("a storage layer") and "RAG" in ex.extract("build a RAG chatbot with FAISS")
    assert json.dumps(ex.category(["scikit-learn", "Python"])) == '"ml_ai"'
