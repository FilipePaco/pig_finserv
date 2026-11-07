import pytest

from pig_finserv.safety.pii import PiiMasker, PiiMaskingError


def test_masker_replaces_structured_pii_and_preserves_safe_text() -> None:
    narrative = (
        "Email jane@example.com or call (212) 555-0100. "
        "My SSN is 123-45-6789, account # AB-12345, and DOB: 01/20/1985. "
        "The card 4111 1111 1111 1111 was charged twice."
    )

    masked = PiiMasker(fingerprint_salt=b"test-salt").mask(narrative)

    assert "jane@example.com" not in masked.text
    assert "212) 555-0100" not in masked.text
    assert "123-45-6789" not in masked.text
    assert "AB-12345" not in masked.text
    assert "01/20/1985" not in masked.text
    assert "4111 1111 1111 1111" not in masked.text
    assert "charged twice" in masked.text
    assert masked.entity_counts == {
        "ACCOUNT_ID": 1,
        "CARD_NUMBER": 1,
        "DATE_OF_BIRTH": 1,
        "EMAIL": 1,
        "PHONE": 1,
        "SSN": 1,
    }
    assert len(masked.input_fingerprint) == 64


def test_masker_fingerprint_is_salted_and_stable_for_one_salt() -> None:
    narrative = "Call me at 212-555-0100"

    first = PiiMasker(fingerprint_salt=b"one").mask(narrative)
    same_salt = PiiMasker(fingerprint_salt=b"one").mask(narrative)
    other_salt = PiiMasker(fingerprint_salt=b"two").mask(narrative)

    assert first.input_fingerprint == same_salt.input_fingerprint
    assert first.input_fingerprint != other_salt.input_fingerprint


def test_masker_replaces_high_signal_person_and_location_candidates_locally() -> None:
    masked = PiiMasker(fingerprint_salt=b"test-salt").mask(
        "My name is Jane Doe and I live in New York, NY. My card fee was unexpected."
    )

    assert "Jane Doe" not in masked.text
    assert "New York, NY" not in masked.text
    assert "card fee" in masked.text
    assert masked.entity_counts["PERSON_CANDIDATE"] == 1
    assert masked.entity_counts["LOCATION_CANDIDATE"] == 1


def test_masker_does_not_mask_non_luhn_long_numbers_as_cards() -> None:
    masked = PiiMasker(fingerprint_salt=b"test-salt").mask("Reference 1234 5678 9012 3456")

    assert "1234 5678 9012 3456" in masked.text
    assert "CARD_NUMBER" not in masked.entity_counts


def test_masker_requires_non_empty_salt_and_text_input() -> None:
    with pytest.raises(PiiMaskingError, match="salt"):
        PiiMasker(fingerprint_salt=b"")

    with pytest.raises(PiiMaskingError, match="text"):
        PiiMasker(fingerprint_salt=b"test-salt").mask(None)  # type: ignore[arg-type]
