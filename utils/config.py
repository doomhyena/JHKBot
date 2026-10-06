from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import discord

from utils.emoji import EmojiKey, emoji_key, parse_emoji


class ConfigError(Exception):
    """Hibás vagy hiányzó konfiguráció esetén dobott kivétel."""


@dataclass(frozen=True)
class ReactionRoleMessage:
    """Egy reaction role üzenet beállításai."""

    message_id: int
    description: str
    roles: dict[EmojiKey, int]
    labels: dict[EmojiKey, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GuildConfig:
    """Egy Discord szerver reaction role konfigurációja."""

    guild_id: int
    messages: dict[int, ReactionRoleMessage]

    def get_role_id(
        self, message_id: int, emoji: discord.PartialEmoji
    ) -> int | None:
        """Visszaadja az üzenet + emoji párhoz tartozó role ID-t."""
        message = self.messages.get(message_id)
        if message is None:
            return None
        return message.roles.get(emoji_key(emoji))

    def all_role_ids(self) -> set[int]:
        """Az összes konfigurált role ID (induláskori ellenőrzéshez)."""
        return {
            role_id
            for message in self.messages.values()
            for role_id in message.roles.values()
        }


@dataclass(frozen=True)
class BotConfig:
    """A bot összes szerverének ellenőrzött konfigurációja."""

    guilds: dict[int, GuildConfig]

    def get_guild(self, guild_id: int) -> GuildConfig | None:
        return self.guilds.get(guild_id)

    def get_role_id(
        self, guild_id: int, message_id: int, emoji: discord.PartialEmoji
    ) -> int | None:
        guild = self.get_guild(guild_id)
        return guild.get_role_id(message_id, emoji) if guild else None


def _parse_id(value: Any, what: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{what}: logikai érték nem lehet ID ({value!r}).")

    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise ConfigError(
            f"{what}: érvénytelen ID ({value!r}). Egész számot várok, "
            "pl. 123456789012345678."
        )

    if not 15 <= len(str(parsed)) <= 20:
        raise ConfigError(
            f"{what}: a(z) {parsed} nem tűnik érvényes Discord ID-nak "
            "(15-20 számjegyűnek kell lennie). Jobb klikk -> 'ID másolása'."
        )
    return parsed


def _parse_message(message_id: int, raw: Any) -> ReactionRoleMessage:
    where = f"messages.{message_id}"

    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: objektumot ({{...}}) várok.")

    description = raw.get("description", "")
    if not isinstance(description, str):
        raise ConfigError(f"{where}.description: szöveget várok.")

    raw_roles = raw.get("roles")
    if not isinstance(raw_roles, dict) or not raw_roles:
        raise ConfigError(
            f"{where}.roles: hiányzik vagy üres. Legalább egy "
            '"emoji": role_id párt meg kell adni.'
        )

    roles: dict[EmojiKey, int] = {}
    labels: dict[EmojiKey, str] = {}

    for raw_emoji, raw_role_id in raw_roles.items():
        emoji_text = raw_emoji.strip()
        if not emoji_text:
            raise ConfigError(f"{where}.roles: üres emoji kulcs.")

        emoji = parse_emoji(emoji_text)
        if emoji.id is None and emoji_text.isascii():
            raise ConfigError(
                f"{where}.roles: a(z) {emoji_text!r} nem érvényes emoji. "
                "Unicode emojit (pl. 👍) vagy custom emojit "
                "(<:nev:123456789012345678>) adj meg. A :shortcode: "
                "forma nem működik."
            )

        key = emoji_key(emoji)
        if key in roles:
            raise ConfigError(
                f"{where}.roles: a(z) {emoji_text!r} emoji többször szerepel."
            )

        roles[key] = _parse_id(raw_role_id, f"{where}.roles[{emoji_text}]")
        labels[key] = str(emoji)

    return ReactionRoleMessage(
        message_id=message_id,
        description=description,
        roles=roles,
        labels=labels,
    )


def parse_config(data: Any) -> BotConfig:
    if not isinstance(data, dict):
        raise ConfigError("A config.json gyökerének objektumnak kell lennie.")

    if "guilds" in data:
        raw_guilds = data["guilds"]
        if not isinstance(raw_guilds, dict):
            raise ConfigError('A "guilds" mezőnek objektumnak kell lennie.')
    else:
        if "guild_id" not in data:
            raise ConfigError('Hiányzik a "guild_id" mező.')
        raw_guilds = {str(data["guild_id"]): {"messages": data.get("messages")}}

    guilds: dict[int, GuildConfig] = {}
    for raw_guild_id, raw_guild in raw_guilds.items():
        guild_id = _parse_id(raw_guild_id, f"guilds[{raw_guild_id}]")
        if not isinstance(raw_guild, dict):
            raise ConfigError(f"guilds.{guild_id}: objektumot várok.")

        raw_messages = raw_guild.get("messages")
        if not isinstance(raw_messages, dict):
            raise ConfigError(
                f"guilds.{guild_id}.messages: objektumot várok."
            )

        messages: dict[int, ReactionRoleMessage] = {}
        for raw_message_id, raw_message in raw_messages.items():
            message_id = _parse_id(
                raw_message_id, f"guilds.{guild_id}.messages[{raw_message_id}]"
            )
            messages[message_id] = _parse_message(message_id, raw_message)
        guilds[guild_id] = GuildConfig(guild_id, messages)

    return BotConfig(guilds=guilds)


def load_config(path: str | Path) -> BotConfig:
    path = Path(path)

    if not path.is_file():
        raise ConfigError(
            f"A konfigurációs fájl nem található: {path.resolve()}"
        )

    try:
        with path.open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"A {path.name} nem érvényes JSON ({exc.lineno}. sor, "
            f"{exc.colno}. oszlop): {exc.msg}"
        ) from exc
    except OSError as exc:
        raise ConfigError(f"A {path.name} nem olvasható: {exc}") from exc

    return parse_config(data)


def save_config(path: str | Path, config: BotConfig) -> None:
    """Elmenti a validált konfigurációt olvasható JSON formában."""
    path = Path(path)
    data = {
        "guilds": {
            str(guild_id): {
                "messages": {
                    str(message_id): {
                        "description": message.description,
                        "roles": {
                            message.labels.get(emoji, str(emoji)): role_id
                            for emoji, role_id in message.roles.items()
                        },
                    }
                    for message_id, message in guild.messages.items()
                },
            }
            for guild_id, guild in config.guilds.items()
        },
    }

    try:
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
            file.write("\n")
    except OSError as exc:
        raise ConfigError(f"A {path.name} nem írható: {exc}") from exc
