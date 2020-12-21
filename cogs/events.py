"""asd"""
# pylint: disable=invalid-name

import asyncio
import re
import traceback
from datetime import datetime
from typing import Type, Union

import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context

from .utils import utils

EGG_COLOR = 0xF6DECF


class Events(Cog):
    """A cog containing the bot's event listeners."""
    def __init__(self, bot: utils.Bot):
        self.bot = bot
        self.previous_e_author = None

    async def display_error(self, ctx: Context, error: Type[commands.CommandError]):
        """Sends an embed with error info to the channel the erroring command was invoked in."""
        if isinstance(error, commands.CommandInvokeError):
            name = error.original.__class__.__name__
            message = error.original.args[0]
        else:
            name = error.__class__.__name__
            message = error.args[0]

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Command exception caught.", icon_url=ctx.me.avatar_url)

        embed.add_field(name="Exception", value=f"``{name}: {message}``", inline=False)

        message = await ctx.send(embed=embed)

        if isinstance(error, commands.NoPrivateMessage):
            return

        await message.add_reaction("*️⃣")

        def owner_check(r: discord.Reaction, u: Union[discord.Member, discord.User]) -> bool:
            return r.emoji == "*️⃣" and u.id == 89425361024073728 and r.message.id == message.id

        try:
            await self.bot.wait_for(
                "reaction_add",
                timeout=10,
                check=owner_check
            )
        except asyncio.TimeoutError:
            return await message.clear_reactions()

        full_traceback = "".join(
            traceback.format_exception(type(error), error, error.__traceback__, chain=True)
        )

        if len(full_traceback) > 2000:
            pages = utils.slicer(full_traceback, 1950)

            await ctx.send(f"Traceback: ```python\n{pages[0]}\n```")
            for page in pages[1:]:
                await ctx.send(f"```python\n{page}\n```")

        else:
            await ctx.send(f"Traceback: ```python\n{full_traceback}\n```")

        return await message.clear_reactions()

    @Cog.listener()
    async def on_command_error(self, ctx: Context, error: Type[commands.CommandError]):
        """Fired when an error is raised during command invocation."""
        if isinstance(error, commands.CommandNotFound) or hasattr(ctx.command, "on_error"):
            return

        await ctx.message.add_reaction("<:oof:663527838812602369>")
        return await self.display_error(ctx, error)

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        """Fired each time a message is sent."""
        channel = message.channel

        if channel.id == 662063429879595009:
            contents = [message.activity, message.application, message.attachments,
                        message.embeds, message.content != "E"]
            if message.author.id == self.previous_e_author or any(i for i in contents):
                return await message.delete()

            self.previous_e_author = message.author.id

        if message.content.lower() == "gg":
            await message.add_reaction("\N{NEGATIVE SQUARED LATIN CAPITAL LETTER B}\ufe0f")

    @Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """Fired when a reaction is added to a message the bot can see."""
        if payload.guild_id != 527932145273143306:
            return

        if payload.cached_message:
            message = payload.cached_message
            content = message.content

            embed = discord.Embed(color=EGG_COLOR, timestamp=datetime.utcnow())
            embed.set_author(name="A message was deleted.", icon_url=message.author.avatar_url)

            contents = []

            if content:
                contents.append(content if len(content) < 1024 else f"{content[:1020]}...")
            if message.attachments:
                if len(message.attachments) == 1:
                    contents.append("[Attachment]")
                else:
                    contents.append(f"[{len(message.attachments)} attachments]")
            if message.embeds:
                if content and any(i in message.content.lower() for i in ("http://", "https://")):
                    pass
                elif len(message.embeds) == 1:
                    contents.append("[Embed]")
                else:
                    contents.append(f"[{len(message.embeds)} embeds]")

            embed.add_field(name="Content", value="\n\n".join(contents), inline=False)
            embed.add_field(name="Channel", value=message.channel.mention, inline=False)

            embed.add_field(
                name="Author",
                value=f"{message.author.mention} ({message.author})",
                inline=False
            )

        else:
            channel = self.bot.get_channel(payload.channel_id)

            embed = discord.Embed(color=EGG_COLOR, timestamp=datetime.utcnow())
            embed.set_author(name="A message was deleted.", icon_url=self.bot.user.avatar_url)

            embed.add_field(name="Channel", value=channel.mention)

        await self.bot.get_channel(662438467204153354).send(embed=embed)

    @Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """Fired when a reaction is removed from a message the bot can see."""
        if not payload.cached_message:
            guild = self.bot.get_guild(527932145273143306)
            member = guild.get_member(int(payload.data["author"]["id"]))

            channel_id = payload.data["channel_id"]
            message_id = payload.data["id"]
            jump_url = f"https://discordapp.com/channels/{guild.id}/{channel_id}/{message_id}"

            if payload.data.get("guild_id") != 527932145273143306 or member.bot:
                return

            embed = discord.Embed(color=EGG_COLOR, timestamp=datetime.utcnow())
            embed.set_author(name="A message was edited.", icon_url=member.avatar_url)

            embed.add_field(name="After", value=payload.data["content"], inline=False)

            embed.add_field(
                name="Channel",
                value=self.bot.get_channel(payload.channel_id).mention,
                inline=False
            )
            embed.add_field(name="Author", value=f"{member.mention} ({member})", inline=False)

        else:
            message = payload.cached_message
            jump_url = message.jump_url

            if message.author.bot or not message.content:
                return

            if not message.guild or message.guild.id != 527932145273143306:
                return

            if message.channel.id == 662063429879595009:
                if payload.data["content"] != "E":
                    await message.delete()

            if not payload.data.get("content") or message.content == payload.data["content"]:
                return

            embed = discord.Embed(color=EGG_COLOR, timestamp=datetime.utcnow())
            embed.set_author(name="A message was edited.", icon_url=message.author.avatar_url)

            embed.add_field(name="Before", value=message.content, inline=False)
            embed.add_field(name="After", value=payload.data["content"], inline=False)
            embed.add_field(
                name="Author",
                value=f"{message.author.mention} ({message.author})",
                inline=False
            )

        embed.description = f"[Jump to message]({jump_url})"
        await self.bot.get_channel(662438467204153354).send(embed=embed)

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id == 662063429879595009:
            channel = self.bot.get_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.remove_reaction(payload.emoji, payload.member)


def setup(bot: utils.Bot):
    """Entry point for bot.load_extension."""
    bot.add_cog(Events(bot))
