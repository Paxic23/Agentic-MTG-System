from __future__ import annotations

from collections.abc import Mapping

# These are deck-building utility categories. They matter for diagnosis, but they
# should not be presented as the deck's central "theme" unless a separate
# strategy strongly supports them.
UTILITY_ROLES = {
    "card draw",
    "ramp / fixing",
    "removal",
    "board wipe",
    "interaction",
    "protection",
    "land",
    "creature",
    "spell",
}

# Synergy themes need repeated support before they deserve to be promoted.
# This prevents decks with one graveyard card or one sacrifice outlet from being
# described as graveyard/sacrifice decks.
SIGNIFICANT_THEME_MIN_COUNT = 4
SIGNIFICANT_THEME_MIN_SHARE = 0.06
CORE_THEME_MIN_COUNT = 8
CORE_THEME_MIN_SHARE = 0.12


def _strength(count: int, denominator: int) -> str:
    share = (count / denominator) if denominator else 0
    if count >= CORE_THEME_MIN_COUNT or share >= CORE_THEME_MIN_SHARE:
        return "core"
    if count >= SIGNIFICANT_THEME_MIN_COUNT or share >= SIGNIFICANT_THEME_MIN_SHARE:
        return "supporting"
    return "minor"


def build_theme_profile(
    role_counts: Mapping[str, int],
    *,
    total_cards: int,
    nonland_cards: int,
) -> dict:
    denominator = max(nonland_cards, 1)
    scored_roles = []
    minor_roles = []
    utility_roles = []

    for role, count in sorted(role_counts.items(), key=lambda item: item[1], reverse=True):
        if count <= 0:
            continue

        share = round(count / denominator, 3)
        item = {
            "role": role,
            "count": count,
            "share_of_nonlands": share,
            "strength": _strength(count, denominator),
        }

        if role in UTILITY_ROLES:
            utility_roles.append(item)
        elif item["strength"] == "minor":
            minor_roles.append(item)
        else:
            scored_roles.append(item)

    return {
        "themes": [item["role"] for item in scored_roles],
        "theme_details": scored_roles,
        "minor_themes": minor_roles,
        "utility_roles": utility_roles,
        "thresholds": {
            "significant_min_count": SIGNIFICANT_THEME_MIN_COUNT,
            "significant_min_share_of_nonlands": SIGNIFICANT_THEME_MIN_SHARE,
            "core_min_count": CORE_THEME_MIN_COUNT,
            "core_min_share_of_nonlands": CORE_THEME_MIN_SHARE,
        },
        "total_cards": total_cards,
        "nonland_cards": nonland_cards,
    }
