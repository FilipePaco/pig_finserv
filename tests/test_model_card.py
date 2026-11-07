from pathlib import Path

from pig_finserv.modeling.model_card import ModelCard


def test_model_card_writes_reproducible_metadata(tmp_path: Path) -> None:
    card = ModelCard(
        "tfidf-v1",
        "snapshot-1",
        "2026.1",
        ((2024, 1),),
        ((2025, 1),),
        ((2025, 7),),
        "sigmoid",
        "cost-1-10-v1",
        42,
    )
    output = tmp_path / "model-card.json"
    card.write(output)
    assert '"model_id": "tfidf-v1"' in output.read_text()
