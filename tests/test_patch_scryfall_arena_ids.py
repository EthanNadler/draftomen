from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from draftomen.carddb import iter_scryfall_default_cards
from scripts.patch_scryfall_arena_ids import main


def _card(*, name: str, number: str, set_code: str = "fra", **extra: Any) -> dict:
    return {
        "name": name,
        "set": set_code,
        "collector_number": number,
        "id": f"{set_code}-{number}-{name}",
        **extra,
    }


def _basic(*, name: str, number: str, games: list[str] | None = None) -> dict:
    return _card(
        name=name,
        number=number,
        type_line=f"Basic Land — {name}",
        games=["paper", "arena"] if games is None else games,
    )


def _run(
    *,
    tmp_path: Path,
    cards: list[dict],
    ratings: Any,
    set_code: str = "FRA",
    extra_args: list[str] | None = None,
) -> tuple[int, list[dict]]:
    bulk = tmp_path / "bulk.jsonl"
    bulk.write_text("".join(json.dumps(c) + "\n" for c in cards), encoding="utf-8")
    ratings_file = tmp_path / "ratings.json"
    ratings_file.write_text(json.dumps(ratings), encoding="utf-8")
    output = tmp_path / "out.jsonl.gz"
    code = main(
        argv=[
            set_code,
            "--ratings-file",
            str(ratings_file),
            "--bulk-file",
            str(bulk),
            "--output",
            str(output),
            *(extra_args or []),
        ]
    )
    rows = (
        list(iter_scryfall_default_cards(bulk_file=output)) if output.exists() else []
    )
    return code, [dict(row) for row in rows]


def test_matched_card_gets_17lands_id(tmp_path: Path) -> None:
    code, rows = _run(
        tmp_path=tmp_path,
        cards=[_card(name="Bolt", number="1")],
        ratings=[{"name": "Bolt", "mtga_id": 111}],
    )

    assert code == 0
    assert rows[0]["arena_id"] == 111


def test_double_faced_card_matches_front_face(tmp_path: Path) -> None:
    code, rows = _run(
        tmp_path=tmp_path,
        cards=[_card(name="Front // Back", number="5")],
        ratings=[{"name": "Front", "mtga_id": 222}],
    )

    assert code == 0
    assert rows[0]["arena_id"] == 222


def test_name_with_spaced_ellipsis_matches_scryfall_name(tmp_path: Path) -> None:
    code, rows = _run(
        tmp_path=tmp_path,
        cards=[_card(name="All Good Things...", number="226")],
        ratings=[{"name": "All Good Things . . .", "mtga_id": 333}],
    )

    assert code == 0
    assert rows[0]["arena_id"] == 333


def test_only_lowest_collector_number_gets_id(tmp_path: Path) -> None:
    cards = [
        _card(name="Bolt", number="10"),
        _card(name="Bolt", number="2a"),
        _card(name="Bolt", number="2"),
        _card(name="Bolt", number="S1"),
    ]
    code, rows = _run(
        tmp_path=tmp_path,
        cards=cards,
        ratings=[{"name": "Bolt", "mtga_id": 333}],
    )

    assert code == 0
    with_id = [row["collector_number"] for row in rows if "arena_id" in row]
    assert with_id == ["2"]


def test_existing_arena_id_is_not_overwritten(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cards = [
        _card(name="Bolt", number="1"),
        _card(name="Bolt", number="2", arena_id=999),
        _card(name="Other", number="3"),
    ]
    code, rows = _run(
        tmp_path=tmp_path,
        cards=cards,
        ratings=[{"name": "Bolt", "mtga_id": 111}, {"name": "Other", "mtga_id": 444}],
    )

    assert code == 0
    assert "arena_id" not in rows[0]
    assert rows[1]["arena_id"] == 999
    assert rows[2]["arena_id"] == 444
    assert "Already set: 1" in capsys.readouterr().out


def test_unmatched_names_are_reported_and_other_sets_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = _card(name="Bolt", number="1", set_code="xyz")
    cards = [_card(name="Bolt", number="1"), other]
    code, rows = _run(
        tmp_path=tmp_path,
        cards=cards,
        ratings=[{"name": "Bolt", "mtga_id": 111}, {"name": "Ghost", "mtga_id": 555}],
    )

    assert code == 0
    assert rows[1] == other
    assert all(row["name"] != "Ghost" for row in rows)
    out = capsys.readouterr().out
    assert "Matched: 1" in out
    assert "  Ghost" in out


def test_no_matches_exits_non_zero(tmp_path: Path) -> None:
    code, rows = _run(
        tmp_path=tmp_path,
        cards=[_card(name="Bolt", number="1", set_code="xyz")],
        ratings=[{"name": "Bolt", "mtga_id": 111}],
    )

    assert code != 0
    assert rows == []


def test_invalid_ratings_file_exits_non_zero(tmp_path: Path) -> None:
    code, rows = _run(
        tmp_path=tmp_path,
        cards=[_card(name="Bolt", number="1")],
        ratings={"name": "Bolt"},
    )

    assert code != 0
    assert rows == []


def test_output_is_gzip_jsonl_readable_by_bulk_reader(tmp_path: Path) -> None:
    code, _ = _run(
        tmp_path=tmp_path,
        cards=[_card(name="Bolt", number="1")],
        ratings=[{"name": "Bolt", "mtga_id": 111}],
    )

    assert code == 0
    with gzip.open(tmp_path / "out.jsonl.gz", mode="rt", encoding="utf-8") as handle:
        assert json.loads(handle.readline())["arena_id"] == 111


def test_basic_lands_get_ids_from_shared_offset(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cards = [
        _card(name="Bolt", number="1"),
        _card(name="Shock", number="2"),
        _basic(name="Mountain", number="10"),
        _basic(name="Forest", number="11"),
        _basic(name="Island", number="12", games=["paper"]),
    ]
    code, rows = _run(
        tmp_path=tmp_path,
        cards=cards,
        ratings=[{"name": "Bolt", "mtga_id": 501}, {"name": "Shock", "mtga_id": 502}],
        extra_args=["--basic-lands"],
    )

    assert code == 0
    assert rows[2]["arena_id"] == 510
    assert rows[3]["arena_id"] == 511
    assert "arena_id" not in rows[4]
    assert "Basic lands: 2" in capsys.readouterr().out


def test_basic_lands_are_left_alone_without_option(tmp_path: Path) -> None:
    code, rows = _run(
        tmp_path=tmp_path,
        cards=[_card(name="Bolt", number="1"), _basic(name="Mountain", number="10")],
        ratings=[{"name": "Bolt", "mtga_id": 501}],
    )

    assert code == 0
    assert "arena_id" not in rows[1]


def test_basic_lands_fail_when_offsets_differ(tmp_path: Path) -> None:
    code, rows = _run(
        tmp_path=tmp_path,
        cards=[
            _card(name="Bolt", number="1"),
            _card(name="Shock", number="2"),
            _basic(name="Mountain", number="10"),
        ],
        ratings=[{"name": "Bolt", "mtga_id": 501}, {"name": "Shock", "mtga_id": 700}],
        extra_args=["--basic-lands"],
    )

    assert code != 0
    assert rows == []


def test_basic_lands_fail_when_derived_id_is_taken(tmp_path: Path) -> None:
    code, rows = _run(
        tmp_path=tmp_path,
        cards=[
            _card(name="Bolt", number="1"),
            _basic(name="Mountain", number="10"),
            _card(name="Elsewhere", number="1", set_code="xyz", arena_id=510),
        ],
        ratings=[{"name": "Bolt", "mtga_id": 501}],
        extra_args=["--basic-lands"],
    )

    assert code != 0
    assert rows == []


def test_basic_lands_fail_when_set_has_none(tmp_path: Path) -> None:
    code, rows = _run(
        tmp_path=tmp_path,
        cards=[_card(name="Bolt", number="1")],
        ratings=[{"name": "Bolt", "mtga_id": 501}],
        extra_args=["--basic-lands"],
    )

    assert code != 0
    assert rows == []
