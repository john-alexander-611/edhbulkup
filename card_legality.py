def is_card_legal_in_identity(card_color_identity: str, commander_identity: str) -> bool:
    """
    True if a card's color identity is legal in a commander's deck (i.e. a
    subset of the commander's color identity, per Commander rules).

    "C" is stored as the colorless sentinel for both cards and commanders
    (never an empty string), but it means two different things depending
    on which side it's on:
      - A colorless CARD ("C") is legal in every deck, since no colors
        means it's trivially a subset of any color identity - including
        a mono-colored or five-color commander.
      - A colorless COMMANDER ("C") can only run colorless cards - nothing
        with real color identity is legal there, since the commander
        itself defines an empty color identity.

    So "C" has to be converted to an actual empty set before doing the
    subset comparison, on whichever side it appears - treating it as a
    literal character would incorrectly restrict colorless cards to only
    colorless commanders.
    """
    card_colors = set() if card_color_identity == "C" else set(card_color_identity)
    commander_colors = set() if commander_identity == "C" else set(commander_identity)
    return card_colors <= commander_colors
