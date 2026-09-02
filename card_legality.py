def is_card_legal_in_identity(card_color_identity: str, commander_identity: str) -> bool:
    """Check whether a card's color identity is a subset of the commander's.

    "C" is the colorless sentinel on both sides and is treated as an empty
    set rather than a literal character (otherwise colorless cards would
    only be legal for colorless commanders).

    Args:
        card_color_identity: Card's color identity, e.g. "WU" or "C".
        commander_identity: Commander's color identity, e.g. "WU" or "C".

    Returns:
        bool: True if the card is legal under the commander's identity.
    """
    card_colors = set() if card_color_identity == "C" else set(card_color_identity)
    commander_colors = set() if commander_identity == "C" else set(commander_identity)
    return card_colors <= commander_colors
