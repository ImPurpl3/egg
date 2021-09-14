"""
MIT License

Copyright (c) 2020 ValkyriaKing711

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
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
        self.previous_number = None

        self.bot.loop.create_task(self.fetch_last_number)

    async def fetch_last_number(self):
        await self.bot.wait_until_ready()
        last_message = (await self.bot.get_channel(662063429879595009).history(limit=5).flatten())[0]
        self.previous_number = int(last_message.content), last_message.author.id

    @Cog.listener()
    async def on_command_error(self, ctx: Context, error: Type[commands.CommandError]):
        """Fired when an error is raised during command invocation."""
        if isinstance(error, commands.CommandNotFound) or hasattr(ctx.command, "on_error"):
            return

        await ctx.message.add_reaction("<:oof:663527838812602369>")
        return await utils.display_error(ctx, error)

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        """Fired each time a message is sent."""
        channel = message.channel

        previous_number, previous_author = self.previous_number

        if channel.id == 662063429879595009:
            contents = [message.activity, message.application, message.attachments,
                        message.embeds, not message.content.isdigit()]
            if message.author.id == previous_author or any(i for i in contents):
                return await message.delete()
            elif int(message.content) != previous_number + 1:
                return await message.delete()

            self.previous_number = previous_number + 1, message.author.id

        if message.content.lower() == "gg":
            await message.add_reaction("\N{NEGATIVE SQUARED LATIN CAPITAL LETTER B}\ufe0f")

    @Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """Fired when a message is deleted."""
        if payload.guild_id != 527932145273143306:
            return

        if payload.cached_message:
            message = payload.cached_message
            content = message.content

            embed = discord.Embed(color=EGG_COLOR, timestamp=datetime.utcnow())
            embed.set_author(name="A message was deleted.", icon_url=message.author.avatar.url)

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
            embed.set_author(name="A message was deleted.", icon_url=self.bot.user.avatar.url)

            embed.add_field(name="Channel", value=channel.mention)

        await self.bot.get_channel(662438467204153354).send(embed=embed)

    @Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """Fired when a message is edited."""
        if not payload.cached_message:
            guild = self.bot.get_guild(527932145273143306)
            member = guild.get_member(int(payload.data["author"]["id"]))

            channel_id = payload.data["channel_id"]
            message_id = payload.data["id"]
            jump_url = f"https://discordapp.com/channels/{guild.id}/{channel_id}/{message_id}"

            if payload.data.get("guild_id") != 527932145273143306 or member.bot:
                return

            if channel_id == 662063429879595009:
                return await (await self.bot.get_channel(channel_id).fetch_message(message_id)).delete()

            embed = discord.Embed(color=EGG_COLOR, timestamp=datetime.utcnow())
            embed.set_author(name="A message was edited.", icon_url=member.avatar.url)

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
                await message.delete()

            if not payload.data.get("content") or message.content == payload.data["content"]:
                return

            embed = discord.Embed(color=EGG_COLOR, timestamp=datetime.utcnow())
            embed.set_author(name="A message was edited.", icon_url=message.author.avatar.url)

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
