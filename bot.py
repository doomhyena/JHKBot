from __future__ import annotations
import discord
import logging
import os
import sys
from discord import app_commands
from discord.ext import commands
from pathlib import Path
from dotenv import load_dotenv
from utils.config import (
    BotConfig,
    ConfigError,
    ReactionRoleMessage,
    load_config,
    parse_config,
    save_config,
)
from utils.emoji import emoji_key, parse_emoji

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"

log = logging.getLogger("reaction_roles")

class PrefixInteractionAdapter:
    """A prefix context minimális Interaction-szerű adaptere."""

    def __init__(self, context: commands.Context) -> None:
        self.guild = context.guild
        self.channel = context.channel
        self.response = self
        self._context = context

    async def send_message(self, content: str, ephemeral: bool = False) -> None:
        await self._context.send(content)


class ReactionRoleBot(commands.Bot):
    """Egyszerű, egy szerverre szabott reaction role bot."""

    def __init__(
        self,
        config: BotConfig,
        config_path: Path,
        command_prefix: str,
        allowed_user_ids: frozenset[int],
    ) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.guild_reactions = True
        intents.message_content = True
        discord.VoiceClient.warn_nacl = False
        discord.VoiceClient.warn_dave = False

        super().__init__(
            command_prefix=command_prefix,
            intents=intents,
            help_command=None,
        )
        self.config = config
        self.config_path = config_path
        self.command_prefix_text = command_prefix
        self.allowed_user_ids = allowed_user_ids
        self._startup_checked = False
        self.reaction_role_group = app_commands.Group(
            name="reaction-role",
            description="Reaction role beállítása",
            guild_only=True,
        )
        self._register_commands()
        self._register_prefix_commands()

    def is_allowed_user(self, user_id: int) -> bool:
        """Csak az ALLOWED_USER_IDS-ben megadott felhasználók kezelhetik a botot."""
        return user_id in self.allowed_user_ids

    def _register_commands(self) -> None:
        allowed_users_only = app_commands.check(
            lambda interaction: self.is_allowed_user(interaction.user.id)
        )

        @self.tree.error
        async def on_app_command_error(
            interaction: discord.Interaction, error: app_commands.AppCommandError
        ) -> None:
            if isinstance(error, app_commands.CheckFailure):
                message = "Ezt a parancsot nem használhatod."
            else:
                log.error("Slash parancshiba (%s): %s", interaction.command, error)
                message = "Hiba történt a parancs végrehajtásakor."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)

        @self.reaction_role_group.command(
            name="add", description="Emojihoz role-t rendel egy üzeneten"
        )
        @allowed_users_only
        async def add_reaction_role(
            interaction: discord.Interaction,
            message_id: str,
            role: discord.Role,
            emoji: str,
            description: str = "",
        ) -> None:
            await self._add_reaction_role(
                interaction, message_id, role, emoji, description
            )

        @self.reaction_role_group.command(
            name="remove", description="Eltávolít egy emoji-role párost"
        )
        @allowed_users_only
        async def remove_reaction_role(
            interaction: discord.Interaction, message_id: str, emoji: str
        ) -> None:
            await self._remove_reaction_role(interaction, message_id, emoji)

        @self.reaction_role_group.command(
            name="reload", description="Újraolvassa a config.json-t"
        )
        @allowed_users_only
        async def reload_reaction_roles(
            interaction: discord.Interaction,
        ) -> None:
            try:
                self.config = load_config(self.config_path)
            except ConfigError as exc:
                await interaction.response.send_message(
                    f"Nem sikerült újraolvasni a konfigurációt: {exc}",
                    ephemeral=True,
                )
                return
            guild_messages = (
                self.config.get_guild(interaction.guild.id).messages
                if interaction.guild is not None
                and self.config.get_guild(interaction.guild.id) is not None
                else {}
            )
            await interaction.response.send_message(
                f"Konfiguráció újratöltve: {len(guild_messages)} üzenet.",
                ephemeral=True,
            )
            if interaction.guild is not None:
                await self._ensure_configured_reactions(interaction.guild)

        @self.tree.command(name="help", description="Megmutatja a bot használatát")
        async def slash_help(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(
                embed=self._help_embed(), ephemeral=True
            )

        self.tree.add_command(self.reaction_role_group)

    def _register_prefix_commands(self) -> None:
        @self.group(name="reaction-role", invoke_without_command=True)
        async def prefix_reaction_role(ctx: commands.Context) -> None:
            await ctx.send(embed=self._help_embed())

        @prefix_reaction_role.command(name="add")
        async def prefix_add(
            ctx: commands.Context,
            message_id: str,
            role: discord.Role,
            emoji: str,
            *,
            description: str = "",
        ) -> None:
            if not await self._prefix_admin_check(ctx):
                return
            await self._add_reaction_role(
                PrefixInteractionAdapter(ctx), message_id, role, emoji, description
            )

        @prefix_reaction_role.command(name="remove")
        async def prefix_remove(
            ctx: commands.Context, message_id: str, emoji: str
        ) -> None:
            if not await self._prefix_admin_check(ctx):
                return
            await self._remove_reaction_role(
                PrefixInteractionAdapter(ctx), message_id, emoji
            )

        @prefix_reaction_role.command(name="reload")
        async def prefix_reload(ctx: commands.Context) -> None:
            if not await self._prefix_admin_check(ctx):
                return
            try:
                self.config = load_config(self.config_path)
            except ConfigError as exc:
                await ctx.send(f"Nem sikerült újraolvasni a konfigurációt: {exc}")
                return
            await self._ensure_configured_reactions(ctx.guild)
            guild_config = self.config.get_guild(ctx.guild.id)
            await ctx.send(
                f"Konfiguráció újratöltve: "
                f"{len(guild_config.messages) if guild_config else 0} üzenet."
            )

        @self.command(name="help")
        async def prefix_help(ctx: commands.Context) -> None:
            await ctx.send(embed=self._help_embed())

    async def _prefix_admin_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            await ctx.send("Ezt a parancsot Discord szerveren használd.")
            return False
        if not self.is_allowed_user(ctx.author.id):
            await ctx.send("Ezt a parancsot nem használhatod.")
            return False
        return True

    def _help_embed(self) -> discord.Embed:
        p = self.command_prefix_text
        return discord.Embed(
            title="Reaction Role súgó",
            description="A bot slash és prefix parancsokkal is használható.",
            color=discord.Color.blurple(),
        ).add_field(
            name="Slash parancsok",
            value=(
                "`/help`\n"
                "`/reaction-role add message_id role emoji [description]`\n"
                "`/reaction-role remove message_id emoji`\n"
                "`/reaction-role reload`"
            ),
            inline=False,
        ).add_field(
            name="Prefix parancsok",
            value=(
                f"`{p}help`\n"
                f"`{p}reaction-role add message_id @role emoji [description]`\n"
                f"`{p}reaction-role remove message_id emoji`\n"
                f"`{p}reaction-role reload`"
            ),
            inline=False,
        ).add_field(
            name="Példa",
            value=(
                f"`{p}reaction-role add 1554900336332771361 @CSharp 💜 C# fejlesztő`\n"
                "Az add parancs elmenti a párost, és ráteszi a reakciót az üzenetre."
            ),
            inline=False,
        ).set_footer(text="Fejlesztő: doomhyena")

    async def on_command_error(
        self, context: commands.Context, error: commands.CommandError
    ) -> None:
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await context.send(
                "Hiányzó parancsparaméter. Írd be: "
                f"`{self.command_prefix_text}help` a használati példákért."
            )
            return

        if isinstance(error, commands.BadArgument):
            await context.send(
                "Nem sikerült értelmezni a paramétert. A role-t említéssel add meg "
                f"(`@Role`), majd próbáld újra. Példa: `{self.command_prefix_text}help`"
            )
            return

        log.error("Prefix parancshiba (%s): %s", context.command, error)
        await context.send(
            "Hiba történt a parancs végrehajtásakor. Írd be: "
            f"`{self.command_prefix_text}help`."
        )

    async def _add_reaction_role(
        self,
        interaction: discord.Interaction,
        message_id_text: str,
        role: discord.Role,
        emoji_text: str,
        description: str,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
            "Ezt a parancsot Discord szerveren használd.",
                ephemeral=True,
            )
            return

        try:
            message_id = int(message_id_text)
            if message_id <= 0:
                raise ValueError
            emoji = parse_emoji(emoji_text)
        except (ValueError, TypeError):
            await interaction.response.send_message(
                "Hibás üzenet ID vagy emoji. Emoji lehet például `🎮` vagy "
                "`<:nev:123456789012345678>`.",
                ephemeral=True,
            )
            return

        if not emoji.name:
            await interaction.response.send_message(
                "Az emoji nem lehet üres.", ephemeral=True
            )
            return

        if self._get_manageable_role(guild, role.id) is None:
            await interaction.response.send_message(
                "Ezt a role-t a bot nem tudja kezelni. Ellenőrizd a Manage Roles "
                "jogosultságot és a role-hierarchiát.",
                ephemeral=True,
            )
            return

        message = await self._find_message(guild, message_id, interaction.channel)

        if message is None:
            await interaction.response.send_message(
                "Nem találom az üzenetet a szerver egyik általam látható "
                "csatornájában sem.",
                ephemeral=True,
            )
            return

        guild_config = self.config.get_guild(guild.id)
        current = guild_config.messages.get(message_id) if guild_config else None
        roles = dict(current.roles) if current else {}
        labels = dict(current.labels) if current else {}
        key = emoji_key(emoji)
        roles[key] = role.id
        labels[key] = str(emoji)
        messages = dict(guild_config.messages) if guild_config else {}
        messages[message_id] = ReactionRoleMessage(
            message_id,
            description or (current.description if current else ""),
            roles,
            labels,
        )
        guild_messages = {
            guild_id: dict(config.messages)
            for guild_id, config in self.config.guilds.items()
        }
        guild_messages[guild.id] = messages
        new_config = self._build_config(guild_messages)

        try:
            save_config(self.config_path, new_config)
            await message.add_reaction(emoji)
        except (ConfigError, discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.send_message(
                f"Nem sikerült menteni vagy reakciót hozzáadni: {exc}",
                ephemeral=True,
            )
            return

        self.config = new_config
        await interaction.response.send_message(
            f"Elmentve: {emoji} -> {role.mention}.", ephemeral=True
        )

    async def _remove_reaction_role(
        self, interaction: discord.Interaction, message_id_text: str, emoji_text: str
    ) -> None:
        try:
            message_id = int(message_id_text)
            emoji = parse_emoji(emoji_text)
        except (ValueError, TypeError):
            await interaction.response.send_message(
                "Hibás üzenet ID vagy emoji.", ephemeral=True
            )
            return

        guild = interaction.guild
        guild_config = self.config.get_guild(guild.id) if guild else None
        current = guild_config.messages.get(message_id) if guild_config else None
        key = emoji_key(emoji)
        if current is None or key not in current.roles:
            await interaction.response.send_message(
                "Ez az emoji-role páros nincs beállítva.", ephemeral=True
            )
            return

        roles = dict(current.roles)
        labels = dict(current.labels)
        roles.pop(key)
        labels.pop(key, None)
        messages = dict(guild_config.messages) if guild_config else {}
        if roles:
            messages[message_id] = ReactionRoleMessage(
                message_id, current.description, roles, labels
            )
        else:
            messages.pop(message_id)

        guild_messages = {
            guild_id: dict(config.messages)
            for guild_id, config in self.config.guilds.items()
        }
        if guild is not None:
            guild_messages[guild.id] = messages
        new_config = self._build_config(guild_messages)
        try:
            save_config(self.config_path, new_config)
        except ConfigError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        self.config = new_config
        await interaction.response.send_message("A beállítás törölve.", ephemeral=True)

    def _build_config(
        self,
        guild_messages: dict[int, dict[int, ReactionRoleMessage]],
    ) -> BotConfig:
        return parse_config(
            {
                "guilds": {
                    str(guild_id): {
                        "messages": {
                            str(item_id): {
                                "description": item.description,
                                "roles": {
                                    item.labels.get(item_key, str(item_key)): item_role
                                    for item_key, item_role in item.roles.items()
                                },
                            }
                            for item_id, item in messages.items()
                        },
                    }
                    for guild_id, messages in guild_messages.items()
                },
            }
        )

    async def on_ready(self) -> None:
        if self._startup_checked:
            log.info("Újracsatlakozva a Discordhoz.")
            return
        self._startup_checked = True

        assert self.user is not None
        await self.tree.sync()
        for guild in self.guilds:
            guild_object = discord.Object(id=guild.id)
            self.tree.copy_global_to(guild=guild_object)
            await self.tree.sync(guild=guild_object)
        log.info("Sikeresen elindult: %s (ID: %s)", self.user, self.user.id)
        for guild in self.guilds:
            self._run_startup_checks(guild)
            await self._ensure_configured_reactions(guild)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Az új szerveren azonnal elérhetővé teszi a slash parancsokat."""
        guild_object = discord.Object(id=guild.id)
        self.tree.copy_global_to(guild=guild_object)
        await self.tree.sync(guild=guild_object)
        log.info("Új szerverhez csatlakoztam: %s (ID: %s)", guild.name, guild.id)

    def _run_startup_checks(self, guild: discord.Guild) -> None:
        log.info("Konfigurált guild: %s (ID: %s)", guild.name, guild.id)

        if not guild.me.guild_permissions.manage_roles:
            log.error(
                "A botnak nincs 'Manage Roles' jogosultsága ezen a szerveren, "
                "így egyetlen role-t sem tud kiosztani."
            )
            return

        guild_config = self.config.get_guild(guild.id)
        role_ids = guild_config.all_role_ids() if guild_config else set()
        ok_count = sum(
            1
            for role_id in role_ids
            if self._get_manageable_role(guild, role_id) is not None
        )
        total = len(role_ids)
        log.info(
            "%d üzenet figyelése, %d/%d role kezelhető.",
            len(guild_config.messages) if guild_config else 0,
            ok_count,
            total,
        )

    @staticmethod
    def _searchable_channels(
        guild: discord.Guild, preferred: object | None = None
    ) -> list[discord.abc.Messageable]:
        """A szerver összes olyan csatornája, ahol üzenet lehet.

        Szöveges, hang- és stage csatornák chatje, valamint az aktív threadek
        (fórumposztok is). Ha van ``preferred`` csatorna (ahol a parancsot
        kiadták), azzal kezd, így az ott lévő üzenetet azonnal megtalálja.
        """
        channels: list[discord.abc.Messageable] = []
        if isinstance(preferred, discord.abc.Messageable) and not isinstance(
            preferred, (discord.DMChannel, discord.GroupChannel)
        ):
            channels.append(preferred)
        channels.extend(guild.text_channels)
        channels.extend(guild.voice_channels)
        channels.extend(guild.stage_channels)
        channels.extend(guild.threads)

        seen: set[int] = set()
        unique: list[discord.abc.Messageable] = []
        for channel in channels:
            if channel.id not in seen:
                seen.add(channel.id)
                unique.append(channel)
        return unique

    async def _find_message(
        self,
        guild: discord.Guild,
        message_id: int,
        preferred_channel: object | None = None,
    ) -> discord.Message | None:
        for channel in self._searchable_channels(guild, preferred_channel):
            try:
                return await channel.fetch_message(message_id)
            except discord.NotFound:
                continue
            except discord.Forbidden:
                continue
            except discord.HTTPException as exc:
                log.warning(
                    "Nem sikerült lekérni a(z) %s üzenetet a(z) '%s' "
                    "csatornából: %s",
                    message_id,
                    channel.name,
                    exc,
                )
        return None

    async def _ensure_configured_reactions(self, guild: discord.Guild) -> None:
        """Megkeresi a konfigurált üzeneteket, és kiteszi rájuk az emojikat."""
        guild_config = self.config.get_guild(guild.id)
        if guild_config is None:
            return

        for message_config in guild_config.messages.values():
            message = await self._find_message(guild, message_config.message_id)

            if message is None:
                log.warning(
                    "A(z) %s konfigurált üzenetet nem találtam a szerver "
                    "csatornái között.",
                    message_config.message_id,
                )
                continue

            for emoji_text in message_config.labels.values():
                try:
                    await message.add_reaction(parse_emoji(emoji_text))
                except discord.Forbidden:
                    log.warning(
                        "Nincs jogosultságom reakciót hozzáadni a(z) %s "
                        "üzenethez.",
                        message_config.message_id,
                    )
                    break
                except discord.HTTPException as exc:
                    log.warning(
                        "Nem sikerült a(z) %s reakciót hozzáadni a(z) %s "
                        "üzenethez: %s",
                        emoji_text,
                        message_config.message_id,
                        exc,
                    )
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        await self._handle_reaction(payload, add=True)

    async def on_raw_reaction_remove(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        await self._handle_reaction(payload, add=False)

    async def _handle_reaction(
        self, payload: discord.RawReactionActionEvent, *, add: bool
    ) -> None:
        if payload.guild_id is None:
            return

        guild_config = self.config.get_guild(payload.guild_id)
        if guild_config is None:
            return

        message_config = guild_config.messages.get(payload.message_id)
        if message_config is None:
            return

        role_id = guild_config.get_role_id(payload.message_id, payload.emoji)
        if role_id is None:
            log.debug(
                "Nem konfigurált emoji (%s) a(z) %s üzeneten, figyelmen kívül.",
                payload.emoji,
                payload.message_id,
            )
            return

        if self.user is not None and payload.user_id == self.user.id:
            return
        if payload.member is not None and payload.member.bot:
            return

        guild = self.get_guild(payload.guild_id)
        if guild is None:
            log.warning(
                "A(z) %s guild nincs a cache-ben (a bot kikerült a "
                "szerverről vagy leállás alatt van a Discord?).",
                payload.guild_id,
            )
            return

        member = await self._resolve_member(guild, payload)
        if member is None or member.bot:
            return

        role = self._get_manageable_role(guild, role_id)
        if role is None:
            return

        if add:
            await self._add_role(member, role, payload)
        else:
            await self._remove_role(member, role, payload)

    async def _resolve_member(
        self, guild: discord.Guild, payload: discord.RawReactionActionEvent
    ) -> discord.Member | None:
        if payload.member is not None:
            return payload.member

        try:
            return await guild.fetch_member(payload.user_id)
        except discord.NotFound:
            log.info(
                "A(z) %s felhasználó már nincs a szerveren, nincs teendő.",
                payload.user_id,
            )
        except discord.HTTPException as exc:
            log.error(
                "Nem sikerült lekérni a(z) %s felhasználót: %s",
                payload.user_id,
                exc,
            )
        return None

    def _get_manageable_role(
        self, guild: discord.Guild, role_id: int
    ) -> discord.Role | None:
        """Visszaadja a role-t, ha létezik és a bot kezelni tudja."""
        role = guild.get_role(role_id)
        if role is None:
            log.error(
                "A(z) %s ID-jú role nem található a szerveren (törölték, vagy "
                "hibás az ID a config.json-ban).",
                role_id,
            )
            return None

        me = guild.me
        if not me.guild_permissions.manage_roles:
            log.error(
                "Nem tudom kezelni a(z) '%s' role-t: nincs 'Manage Roles' "
                "jogosultságom.",
                role.name,
            )
            return None

        if role.is_default() or role.managed:
            log.error(
                "A(z) '%s' role nem osztható ki kézzel (@everyone, vagy "
                "integráció / bot / booster által kezelt role).",
                role.name,
            )
            return None

        if role >= me.top_role:
            log.error(
                "A(z) '%s' role (pozíció: %d) nem alacsonyabb a bot legfelső "
                "role-jánál ('%s', pozíció: %d). Húzd a bot role-ját "
                "feljebb a Szerverbeállítások -> Szerepkörök listában.",
                role.name,
                role.position,
                me.top_role.name,
                me.top_role.position,
            )
            return None

        return role

    async def _add_role(
        self,
        member: discord.Member,
        role: discord.Role,
        payload: discord.RawReactionActionEvent,
    ) -> None:
        if role in member.roles:
            log.info("%s már rendelkezik a(z) '%s' role-lal.", member, role.name)
            return

        try:
            await member.add_roles(
                role, reason=f"Reaction role: {payload.emoji} hozzáadva"
            )
        except discord.Forbidden:
            log.error(
                "Nincs jogosultságom a(z) '%s' role-t hozzáadni %s számára "
                "(Manage Roles / role hierarchia).",
                role.name,
                member,
            )
        except discord.HTTPException as exc:
            log.error(
                "Discord API hiba a(z) '%s' role hozzáadásakor (%s): %s",
                role.name,
                member,
                exc,
            )
        else:
            log.info("+ '%s' role hozzáadva: %s", role.name, member)

    async def _remove_role(
        self,
        member: discord.Member,
        role: discord.Role,
        payload: discord.RawReactionActionEvent,
    ) -> None:
        if role not in member.roles:
            log.info("%s nem rendelkezik a(z) '%s' role-lal.", member, role.name)
            return

        try:
            await member.remove_roles(
                role, reason=f"Reaction role: {payload.emoji} eltávolítva"
            )
        except discord.Forbidden:
            log.error(
                "Nincs jogosultságom a(z) '%s' role-t elvenni %s felhasználótól "
                "(Manage Roles / role hierarchia).",
                role.name,
                member,
            )
        except discord.HTTPException as exc:
            log.error(
                "Discord API hiba a(z) '%s' role elvételekor (%s): %s",
                role.name,
                member,
                exc,
            )
        else:
            log.info("- '%s' role elvéve: %s", role.name, member)

    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        guild_config = (
            self.config.get_guild(payload.guild_id) if payload.guild_id else None
        )
        if guild_config and payload.message_id in guild_config.messages:
            log.warning(
                "Egy konfigurált reaction role üzenetet (%s) töröltek. "
                "Távolítsd el a config.json-ból, vagy cseréld az új üzenet "
                "ID-jára.",
                payload.message_id,
            )

    async def on_guild_role_delete(self, role: discord.Role) -> None:
        guild_config = self.config.get_guild(role.guild.id)
        if guild_config and role.id in guild_config.all_role_ids():
            log.warning(
                "A konfigurált '%s' role-t (%s) törölték a szerverről. "
                "Frissítsd a config.json-t.",
                role.name,
                role.id,
            )


def main() -> int:
    discord.utils.setup_logging(level=logging.INFO, root=True)

    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == TOKEN_PLACEHOLDER:
        log.error(
            "Hiányzik a DISCORD_TOKEN. Hozd létre a .env fájlt a "
            ".env.example alapján, és írd bele a bot tokenjét."
        )
        return 1

    command_prefix = os.getenv("BOT_PREFIX", "").strip()
    if not command_prefix:
        log.warning(
            "A BOT_PREFIX nincs megadva a .env fájlban, az alapértelmezett "
            "'%s' prefix lesz használva.",
            DEFAULT_PREFIX,
        )
        command_prefix = DEFAULT_PREFIX

    try:
        allowed_user_ids = frozenset(
            int(part)
            for part in os.getenv("ALLOWED_USER_IDS", "").replace(" ", "").split(",")
            if part
        )
    except ValueError:
        log.error(
            "Hibás ALLOWED_USER_IDS a .env fájlban. Vesszővel elválasztott "
            "Discord user ID-kat adj meg, pl.: 123456789012345678,234567890123456789"
        )
        return 1
    if not allowed_user_ids:
        log.warning(
            "Az ALLOWED_USER_IDS nincs megadva a .env fájlban, így senki sem "
            "használhatja a reaction-role parancsokat."
        )

    config_path = Path(os.getenv("CONFIG_PATH", DEFAULT_CONFIG_PATH))
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        log.error("Hibás konfiguráció (%s): %s", config_path.name, exc)
        return 1

    log.info(
        "Konfiguráció betöltve: %d guild, %d üzenet.",
        len(config.guilds),
        sum(len(guild.messages) for guild in config.guilds.values()),
    )

    bot = ReactionRoleBot(config, config_path, command_prefix, allowed_user_ids)
    try:
        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        log.error(
            "Sikertelen bejelentkezés: a DISCORD_TOKEN érvénytelen. "
            "Generálj újat a Developer Portalon (Bot -> Reset Token)."
        )
        return 1
    except discord.HTTPException as exc:
        log.error("Nem sikerült csatlakozni a Discordhoz: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
