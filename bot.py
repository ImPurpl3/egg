"""Main file for egg bot."""
# pylint: disable=invalid-name
import os

import aiohttp
import discord
from discord import Intents
from discord.ext import commands
from discord.ext.commands import when_mentioned_or

from bot_webserver import WebServer
from cogs.utils import utils


bot = utils.Bot(command_prefix=when_mentioned_or("egg ", "Egg "), intents=Intents.all())
bot.hook_db("data.db")


@bot.check
async def guild_only(ctx: commands.Context):
    if ctx.author.id == bot.owner_id:
        return True

    if not ctx.guild:
        raise commands.NoPrivateMessage("Commands cannot be used in DMs.")

    return True


@bot.event
async def on_ready():
    """Fired each time bot's connection to Discord is opened and ready."""
    if not hasattr(bot, "web"):
        bot.web = WebServer(bot)

    if not hasattr(bot, "session"):
        bot.session = aiohttp.ClientSession()

    for extension in os.listdir("./cogs"):
        if extension.endswith(".py") and not extension.isupper():
            try:
                bot.load_extension(f"cogs.{extension[:-3]}")
                print(f"{extension} loaded successfully.")
            except commands.ExtensionError as exc:
                print(f"An error occurred while loading {extension}:\n{exc}")

    await bot.change_presence(
        activity=discord.Activity(
            name="egg help \N{FLUSHED FACE}",
            type=discord.ActivityType.listening
        ),
        status=discord.Status.dnd
    )

    print("Bot is ready.\n")

bot.load_extension("jishaku")
bot.run(os.getenv("EGG_TOKEN"))
bot.loop.create_task(bot.web.runner.cleanup())
