"""An extension containing the cog for owner commands."""
import os
from typing import Type

import discord
from discord.ext import commands
from discord.ext.commands import CheckFailure, Cog, CommandError, Context, NotOwner

from .utils import utils

EGG_COLOR = 0xF6DECF


class Owner(Cog):
    """A cog containing owner-only commands."""
    def __init__(self, bot: utils.Bot):
        self.bot = bot

    async def cog_check(self, ctx: Context):
        return await ctx.bot.is_owner(ctx.author)

    async def cog_command_error(self, ctx: Context, error: Type[CommandError]) -> None:
        if isinstance(error, CheckFailure):
            raise NotOwner("You do not own this bot.")
        raise error

    @commands.command()
    async def reload(self, ctx: Context, extension: utils.ExtensionConverter) -> None:
        """Reloads an extension (or all extensions)"""
        if extension != "all":
            try:
                try:
                    self.bot.reload_extension(extension)
                except commands.ExtensionNotLoaded:
                    self.bot.load_extension(extension)
            except commands.ExtensionFailed as exc:
                embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                embed.set_author(name=f"Extension failed to load.", icon_url=ctx.me.avatar_url)
                embed.add_field(name="Extension", value=f"{extension[5:]}.py")

                embed.add_field(
                    name="Error",
                    value=f"``{exc.original.__class__.__name__}: {str(exc.original)}``"
                )

                return await ctx.send(embed=embed)

            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name=f"Extension reloaded.", icon_url=ctx.me.avatar_url)
            embed.add_field(name="Extension", value=f"{extension[5:]}.py")
            return await ctx.send(embed=embed)

        failed_extensions = []

        for ext in os.listdir("./cogs"):
            if not ext.endswith(".py"):
                continue
            try:
                try:
                    self.bot.reload_extension(f"cogs.{ext[:-3]}")
                except commands.ExtensionFailed as exc:
                    failed_extensions.append(f"{ext}: ``{exc.original.__class__.__name__}``")
            except commands.ExtensionNotLoaded:
                try:
                    self.bot.load_extension(f"cogs.{ext[:-3]}")
                except commands.ExtensionFailed as exc:
                    failed_extensions.append(f"{ext}: ``{exc.original.__class__.__name__}``")

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="All extensions reloaded.", icon_url=ctx.me.avatar_url)

        if failed_extensions:
            embed.description = "There were errors."
            embed.add_field(name="Failed", value="\n".join(failed_extensions))

        await ctx.send(embed=embed)

    @commands.command(aliases=["logout"])
    async def shutdown(self, ctx: Context):
        """Logs the bot out and does some cleanup."""
        await ctx.message.add_reaction("\N{FLUSHED FACE}")
        await self.bot.shutdown()


def setup(bot: utils.Bot):
    """Entry point for bot.load_extension."""
    bot.add_cog(Owner(bot))
