"""Tests for smart namer, TF-IDF extraction, sanitization, length limiting, and collisions."""

from pathlib import Path
import pytest

from sloth_sorter.namer import (
    extract_keywords_tfidf,
    generate_smart_name,
    resolve_smart_collision,
    sanitize_name_component,
)


def test_sanitize_name_component():
    assert sanitize_name_component("Electricity Bill #123!") == "electricity_bill_123"
    assert sanitize_name_component("___Hello___World___") == "hello_world"
    assert sanitize_name_component(" spaces  and   tabs ") == "spaces_and_tabs"
    assert sanitize_name_component("Special @#$% Characters") == "special_characters"


def test_extract_keywords_tfidf():
    text = (
        "Electric utility invoice statement. Total payment due for electricity bill is $85.00. "
        "Customer account billing information."
    )
    keywords = extract_keywords_tfidf(text, top_k=3)
    assert len(keywords) > 0
    # Expected key domain terms to appear in keywords
    assert any(k in ["electric", "electricity", "utility", "invoice", "statement", "bill", "billing"] for k in keywords)


def test_generate_smart_name():
    text = "Electric utility bill payment invoice statement due today."
    # Fixed timestamp: 2024-03-15 UTC -> 1710460800
    mtime = 1710460800.0
    name = generate_smart_name("doc123.pdf", text, mtime)
    assert name.startswith("2024-03_")
    assert name.endswith(".pdf")
    assert " " not in name
    assert len(name) <= 80


def test_generate_smart_name_empty_text():
    # Empty text keeps original filename
    name = generate_smart_name("my_original_file.pdf", "", 1710460800.0)
    assert name == "my_original_file.pdf"

    name2 = generate_smart_name("image.png", "   ", 1710460800.0)
    assert name2 == "image.png"


def test_generate_smart_name_max_length_limit():
    # Generate very long keywords
    long_text = "supercalifragilisticexpialidocious " * 50
    name = generate_smart_name("test.docx", long_text, 1710460800.0, max_length=80)
    assert len(name) <= 80
    assert name.endswith(".docx")


def test_resolve_smart_collision(tmp_path):
    dest_dir = tmp_path / "Invoices"
    dest_dir.mkdir()

    def norm_fn(p):
        return str(p.resolve()).lower()

    # Create file that already exists
    existing = dest_dir / "2024-03_electric_bill.pdf"
    existing.write_text("existing")

    src = tmp_path / "incoming.pdf"
    claimed = set()

    # First candidate should resolve with (1)
    resolved_1 = resolve_smart_collision(
        dest_dir=dest_dir,
        candidate_name="2024-03_electric_bill.pdf",
        src_path=src,
        claimed_destinations=claimed,
        normalize_key_fn=norm_fn,
        max_length=80,
    )
    assert resolved_1.name == "2024-03_electric_bill (1).pdf"
    assert len(resolved_1.name) <= 80

    claimed.add(norm_fn(resolved_1))

    # Second candidate should resolve with (2)
    resolved_2 = resolve_smart_collision(
        dest_dir=dest_dir,
        candidate_name="2024-03_electric_bill.pdf",
        src_path=src,
        claimed_destinations=claimed,
        normalize_key_fn=norm_fn,
        max_length=80,
    )
    assert resolved_2.name == "2024-03_electric_bill (2).pdf"
    assert len(resolved_2.name) <= 80
