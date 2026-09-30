"""Emoji-összehasonlítás segédfüggvényei.

A Unicode és a custom (szerver-) emojikat nem lehet megbízhatóan sima
string-összehasonlítással kezelni:

* Custom emojinál a név bármikor átnevezhető, az ID viszont állandó,
  ezért ott az ID alapján hasonlítunk.
* Unicode emojinál ugyanaz az emoji érkezhet "variation selector"
  (U+FE0F) karakterrel vagy anélkül (pl. "❤️" vs. "❤"), ezért ezt
  a karaktert kiszűrjük.
"""

from __future__ import annotations

import discord

# Láthatatlan "variation selector-16" karakter, ami egyes emojik végén szerepel.
_VARIATION_SELECTOR = "️"

# Egy emoji összehasonlítási kulcsa: custom emojinál int (ID), Unicode-nál str.
EmojiKey = int | str


def emoji_key(emoji: discord.PartialEmoji) -> EmojiKey:
    """Visszaad egy stabil kulcsot, amivel két emoji összehasonlítható."""
    if emoji.id is not None:
        return emoji.id
    return (emoji.name or "").replace(_VARIATION_SELECTOR, "")


def parse_emoji(value: str) -> discord.PartialEmoji:
    """Emoji beolvasása a config.json-ban megadott szövegből.

    Elfogadott formátumok:
        "👍"                       -> Unicode emoji
        "<:valami:123456789012345678>"  -> custom emoji
        "<a:valami:123456789012345678>" -> animált custom emoji
        "valami:123456789012345678"     -> custom emoji (rövid forma)
    """
    return discord.PartialEmoji.from_str(value.strip())
