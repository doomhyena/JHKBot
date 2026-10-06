from __future__ import annotations

import discord

_VARIATION_SELECTOR = "️"

EmojiKey = int | str


def emoji_key(emoji: discord.PartialEmoji) -> EmojiKey:
    """Visszaad egy stabil kulcsot, amivel két emoji összehasonlítható."""
    if emoji.id is not None:
        return emoji.id
    return (emoji.name or "").replace(_VARIATION_SELECTOR, "")


def parse_emoji(value: str) -> discord.PartialEmoji:
    """Emoji beolvasása a config.json-ban megadott szövegből.

    Elfogadott formátumok:
        "👍" -> Unicode emoji
        "<:valami:123456789012345678>" -> custom emoji
        "<a:valami:123456789012345678>" -> animált custom emoji
        "valami:123456789012345678"
    """
    return discord.PartialEmoji.from_str(value.strip())
