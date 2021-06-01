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
import os

import aiohttp
import discord
from discord import Intents
from discord.ext import commands
from discord.ext.commands import when_mentioned_or

from bot_webserver import WebServer
from cogs.utils import utils

FIRST_READY = True

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
    global FIRST_READY
    if not FIRST_READY:
        FIRST_READY = False
        print("Reconnected.")
        return

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
