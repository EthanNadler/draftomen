from __future__ import annotations

from draftomen.carddb import CardDatabase, CardFace, CardInfo
from draftomen.splash import infer_splash_state, land_mana_colors


def _land(
    *,
    name: str,
    type_line: str = "Land",
    oracle_text: str | None = None,
    produced_mana: tuple[str, ...] = (),
    faces: tuple[CardFace, ...] = (),
    grp_id: int = 1,
) -> CardInfo:
    return CardInfo(
        grp_id=grp_id,
        name=name,
        colors=(),
        mana_value=0.0,
        rarity="rare",
        types=("Land",),
        produced_mana=produced_mana,
        oracle_text=oracle_text,
        type_line=type_line,
        faces=faces,
    )


def test_token_creating_land_does_not_count_token_mana() -> None:
    card = _land(
        name="Gaseous Anomaly",
        oracle_text=(
            "{T}: Add {C}.\n{5}{U}, Sacrifice this land: Create a New Planet "
            'token. It has "{T}: Add one mana of any color."'
        ),
        produced_mana=("W", "U", "B", "R", "G"),
    )

    assert land_mana_colors(card=card) == ()


def test_choose_a_color_ability_does_not_count_as_fixing() -> None:
    card = _land(
        name="Three Tree City",
        oracle_text=(
            "{T}: Add {C}.\n{2}, {T}: Choose a color. This land becomes that "
            "color until end of turn. Add one mana of that color."
        ),
        produced_mana=("W", "U", "B", "R", "G"),
    )

    assert land_mana_colors(card=card) == ()


def test_quoted_granted_ability_is_ignored() -> None:
    card = _land(
        name="Forgotten Monument",
        oracle_text=(
            "{T}: Add {C}.\nCaves you control have "
            '"{T}: Add one mana of any color."'
        ),
        produced_mana=("W", "U", "B", "R", "G"),
    )

    assert land_mana_colors(card=card) == ()


def test_exiled_card_colors_land_is_ignored() -> None:
    card = _land(
        name="Pit of Offerings",
        oracle_text=(
            "{T}: Add {C}.\n{T}: Add one mana of any of the exiled cards' colors."
        ),
        produced_mana=("W", "U", "B", "R", "G"),
    )

    assert land_mana_colors(card=card) == ()


def test_land_keeps_its_own_colored_mana_next_to_granted_ability() -> None:
    card = _land(
        name="The World Tree",
        oracle_text=(
            "{T}: Add {G}.\nAs long as you control six or more lands, lands "
            'you control have "{T}: Add one mana of any color."'
        ),
        produced_mana=("W", "U", "B", "R", "G"),
    )

    assert land_mana_colors(card=card) == ("G",)


def test_modal_land_unions_colors_of_both_faces() -> None:
    card = _land(
        name="Blightstep Pathway // Searstep Pathway",
        type_line="Land // Land",
        produced_mana=("R", "B"),
        faces=(
            CardFace(name="Blightstep Pathway", type_line="Land", oracle_text="{T}: Add {B}."),
            CardFace(name="Searstep Pathway", type_line="Land", oracle_text="{T}: Add {R}."),
        ),
    )

    assert land_mana_colors(card=card) == ("B", "R")


def test_shock_land_reads_colors_from_basic_land_types() -> None:
    card = _land(
        name="Overgrown Tomb",
        type_line="Land — Swamp Forest",
        oracle_text="As this land enters, you may pay 2 life. If you don't, it enters tapped.",
        produced_mana=("B", "G"),
    )

    assert land_mana_colors(card=card) == ("B", "G")


def test_reminder_text_mana_abilities_are_kept() -> None:
    card = _land(
        name="Typed Dual",
        type_line="Land — Island Mountain",
        oracle_text="({T}: Add {U} or {R}.)\nThis land enters tapped.",
        produced_mana=("U", "R"),
    )

    assert land_mana_colors(card=card) == ("U", "R")


def test_chosen_color_land_trusts_produced_mana() -> None:
    card = _land(
        name="Uncharted Haven",
        oracle_text="{T}: Add one mana of the chosen color.",
        produced_mana=("G", "W"),
    )

    assert land_mana_colors(card=card) == ("W", "G")


def test_unreadable_land_text_falls_back_to_produced_mana() -> None:
    card = _land(
        name="Evolving Wilds",
        oracle_text="{T}, Sacrifice this land: Search your library for a basic land card.",
    )

    assert land_mana_colors(card=card) == ()


def test_land_without_oracle_text_falls_back_to_produced_mana() -> None:
    card = _land(name="Plain Fixer", produced_mana=("R", "W"))

    assert land_mana_colors(card=card) == ("W", "R")


def test_non_land_card_returns_ordered_produced_mana() -> None:
    card = CardInfo(
        grp_id=1,
        name="Mana Elf",
        colors=("G",),
        mana_value=1.0,
        rarity="common",
        types=("Creature",),
        produced_mana=("G", "W"),
        oracle_text="{T}: Add {G} or {W}.",
        type_line="Creature — Elf",
    )

    assert land_mana_colors(card=card) == ("W", "G")


def _fixing_state_for(*, land: CardInfo, color: str) -> int:
    database = CardDatabase(cards={land.grp_id: land})
    state = infer_splash_state(
        pool_grp_ids=(land.grp_id,),
        card_database=database,
        ratings_data=None,
        base_pair="WU",
        enabled=True,
    )
    return state.fixing_for(color=color)


def test_splash_planning_ignores_token_only_land_but_counts_dual() -> None:
    token_land = _land(
        name="Gaseous Anomaly",
        oracle_text='{T}: Add {C}.\n{5}{U}: Create a token with "{T}: Add one mana of any color."',
        produced_mana=("W", "U", "B", "R", "G"),
    )
    dual = _land(
        name="Red Green Dual",
        oracle_text="{T}: Add {R} or {G}.",
        produced_mana=("R", "G"),
    )

    assert _fixing_state_for(land=token_land, color="R") == 0
    assert _fixing_state_for(land=dual, color="R") == 1
