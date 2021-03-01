"""Utility functions and other helper things for the bot."""
import io
import math
import os
import re
from datetime import datetime
from sqlite3 import Row
from typing import Any, List, Iterable, Sequence, Tuple, Union

import parsedatetime as pdt
from aiohttp import ClientSession
from discord import Embed, Member, NotFound, User
from discord.ext import commands
from discord.ext.commands import BadArgument, BucketType, Context, Converter, CooldownMapping
from discord.utils import find
from PIL import Image

from . import asqlite


class Database:
    """Shortcuts for various asqlite cursor methods."""
    def __init__(self, path) -> None:
        self.path = path

    async def execute(self, query: str, *parameters) -> None:
        """Executes an SQL query."""
        async with asqlite.connect(self.path) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, *parameters)

    async def executemany(self, query: str, parameter_seq: Sequence[Sequence[Any]]) -> None:
        """Executes a query for all parameter sequences."""
        async with asqlite.connect(self.path) as connection:
            async with connection.cursor() as cursor:
                await cursor.executemany(query, parameter_seq)

    async def executescript(self, script: str) -> None:
        """Executes an SQL script."""
        async with asqlite.connect(self.path) as connection:
            async with connection.cursor() as cursor:
                await cursor.executescript(script)

    async def fetchall(self, query: str, *parameters) -> List[Row]:
        """Executes an SQL query and fetches all returned rows."""
        async with asqlite.connect(self.path) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, *parameters)
                return await cursor.fetchall()

    async def fetchmany(self, query: str, *parameters, size: int = None) -> List[Row]:
        """Executes an SQL query and fetches the desired amount of returned rows."""
        async with asqlite.connect(self.path) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, *parameters)
                return await cursor.fetchmany(size)

    async def fetchone(self, query: str, *parameters) -> Row:
        """Executes an SQL query and fetches the first returned row."""
        async with asqlite.connect(self.path) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(query, *parameters)
                return await cursor.fetchone()


class Bot(commands.Bot):
    """Subclass of commands.Bot containing various helper attributes."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = None  # pylint: disable=invalid-name
        self.session = ClientSession()

        self.xp_cooldown = CooldownMapping.from_cooldown(1, 60, BucketType.member)

        self.players = {}

        self.prefixes = []
        self.welcome_message = None

    def hook_db(self, path: str) -> Database:
        """Hooks a database wrapper to the Bot instance"""
        self.db = Database(path)
        return self.db

    async def shutdown(self):
        """Closes the bot's aiohttp session and logs out of Discord."""
        await self.session.close()
        await self.logout()


class ExtensionConverter(Converter):  # pylint: disable=too-few-public-methods
    """Converts an argument to a valid extension name."""
    async def convert(self, ctx: Context, argument: str):
        """Handles the conversion."""
        extensions = [
            f"cogs.{ext[:-3]}" for ext in os.listdir("./cogs") if ext.endswith(".py")
        ]
        arg = argument.lower()

        if arg == "all":
            return arg

        if arg in extensions:
            return arg

        if not arg.startswith("cogs."):
            with_folder = f"cogs.{arg}"

            if with_folder in extensions:
                return with_folder

        raise BadArgument(f"Extension \"{argument}\" was not found.")


class GuaranteedUser(commands.Converter):
    """A converter for getting a User or Member by any means possible."""
    # pylint: disable=too-few-public-methods
    async def convert(self, ctx: commands.Context, argument: str) -> Union[Member, User]:
        """Handles the conversion."""
        try:
            user = await commands.MemberConverter().convert(ctx, argument)
        except BadArgument:
            try:
                user = await commands.UserConverter().convert(ctx, argument)
            except BadArgument:
                try:
                    user = await ctx.bot.fetch_user(argument)
                except Exception:
                    raise BadArgument(f"Member or User \"{argument}\" was not found.")
        return user


class RankedUser(commands.Converter):  # pylint: disable=too-few-public-methods
    """Gets a Member using MemberConverter or a Member or User by leaderboard index.
       If an index is given and the user does not exist on Discord, returns the user's Row."""
    async def convert(self, ctx: commands.Context, argument: str) -> Union[Member, User, Row]:  # pylint: disable=too-many-branches,too-many-return-statements
        """Handles the conversion."""
        try:
            return await commands.MemberConverter().convert(ctx, argument)
        except BadArgument:
            if not re.fullmatch(r"(?:\#?\s*\d+|first|last)", argument, flags=re.IGNORECASE):
                raise BadArgument(f"Member \"{argument}\" not found")

            users = await ctx.bot.db.fetchall("SELECT * FROM levels ORDER BY xp DESC")
            ids = [row["id"] for row in users]

            try:
                if (user_id := int(argument.lstrip())) in ids:  # pylint: disable=superfluous-parens
                    user = await ctx.bot.fetch_user(user_id)

                    if re.fullmatch(r"Deleted User [0-9a-f]+", user.name, flags=re.IGNORECASE):
                        return find(lambda row: row["id"] == user_id, users)

                    return user

            except ValueError:
                pass

            if argument.lower() == "first":
                index = 0
            elif argument.lower() == "last":
                index = len(users) - 1
            else:
                index = int(argument.lstrip("# ")) - 1

                if index >= len(users):
                    raise BadArgument(f"Leaderboard index #{index + 1} out of range")
                if index < 0:
                    raise BadArgument(f"Leaderboard index must be greater than 0.")

            user_id = ids[index]

            if member := ctx.guild.get_member(user_id):
                return member

            try:
                user = await ctx.bot.fetch_user(user_id)

                if re.fullmatch(r"Deleted User [0-9a-f]+", user.name, flags=re.IGNORECASE):
                    return find(lambda row: row["id"] == user_id, users)

                return user

            except NotFound:
                return find(lambda row: row["id"] == user_id, users)


def slicer(item: Iterable, per: int) -> list:
    """Slices an iterable into parts, each part containing per items."""
    sliced = []

    for i in range(0, len(item), per):
        sliced.append(item[i:i + per])

    return sliced


def get_luminance(r, g, b, a=1) -> float:  # pylint: disable=invalid-name
    """Gets luminance from an RGB value.
       Source: https://github.com/CuteFwan/Koishi"""
    return (0.299 * r + 0.587 * g + 0.114 * b) * a


def gifmap(im2, im1) -> io.BytesIO:
    """Rearranges image 1's pixels to look like image 2.
       Credit: https://github.com/CuteFwan/Koishi"""
    # pylint: disable=invalid-name, too-many-locals
    im1 = Image.open(im1).resize((256, 256), resample=Image.BICUBIC)
    im2 = Image.open(im2).resize((256, 256), resample=Image.BICUBIC)

    im1data = im1.load()
    im1data = [[(x, y), im1data[x, y]] for x in range(256) for y in range(256)]
    im1data.sort(key=lambda c: get_luminance(*c[1]))

    im2data = im2.load()
    im2data = [[(x, y), im2data[x, y]] for x in range(256) for y in range(256)]
    im2data.sort(key=lambda c: get_luminance(*c[1]))

    frames = []
    for multiplier in range(-10, 11):
        m = 1 - (1 / (1 + (1.7 ** -multiplier)))

        base = Image.new("RGBA", (256, 256))
        basedata = base.load()
        for i, d in enumerate(im1data):
            x1, y1 = d[0]
            x2, y2 = im2data[i][0]
            x, y = round(x1 + (x2 - x1) * m), round(y1 + (y2 - y1) * m)
            basedata[x, y] = im2data[i][1]
        frames.append(base)

    frames = frames + frames[::-1]

    b = io.BytesIO()
    frames[0].save(b, "gif", save_all=True, append_images=frames[1:], loop=0, duration=60)
    b.seek(0)
    return b


def display_time(seconds: Union[float, int], *, precision: str = "m") -> str:
    """Converts seconds to a human readable form.
       Precision can be "m", "h" or "d".
       m = "X minutes and Y seconds"
       h = "X hours, Y minutes and Z seconds"
       d = "X days, Y hours, Z minutes and N seconds
    """
    if seconds < 1:
        return "0 seconds"

    if seconds < 0:
        raise ValueError("can't convert negative seconds")

    if precision.lower() == "d":
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
    elif precision.lower() == "h":
        days = 0
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
    elif precision.lower() == "m":
        days = 0
        hours = 0
        minutes, seconds = divmod(seconds, 60)
    else:
        raise ValueError(f"invalid precision: expected \"m\", \"h\" or \"d\", got \"{precision}\"")

    values = {
        "days": round(days),
        "hours": round(hours),
        "minutes": round(minutes),
        "seconds": round(seconds)
    }
    output = []

    for time, value in values.items():
        if value == 0:
            continue
        output.append(f"{value} {time[:-1] if time == 1 else time}")

    return f"{', '.join(output[:-1])} and {output[-1]}"


def format_seconds(seconds: Union[float, int]):
    if seconds == 0:
        return "0 seconds"

    if isinstance(seconds, float):
        seconds = math.ceil(seconds)

    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = {"hours": hours, "minutes": minutes, "seconds": seconds}
    output = []

    for part, amount in parts.items():
        if amount == 0:
            continue
        output.append(f"{amount} {part if amount > 1 else part[:-1]}")

    if len(output) == 1:
        return output[0]

    return f"{', '.join(output[:-1])} and {output[-1]}"


def plural(word: str, i: int) -> str:
    """Returns either "word" or "words" based on the number."""
    return f"{word}{'' if i == 1 else 's'}"


class BaseEmbed(Embed):
    def __init__(self, ctx: Context, *args, **kwargs):
        super().__init__(
            color=0xF6DECF,
            timestamp=ctx.message.created_at,
            **kwargs)


def format_time(seconds: Union[float, int]):
    seconds = int(seconds)

    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def parse_time(text: str) -> Tuple[datetime, str]:
    """Parses a time delta from the given text and returns
       a datetime and the remaining text.
    """
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)
    now = datetime.utcnow()
    remaining = None

    if text.endswith("from now"):
        text = text[:-8].strip()

    elements = calendar.nlp(text, sourceTime=now)
    if elements is None or len(elements) == 0:
        raise ValueError("could not parse time")

    dt, status, begin, end, dt_string = elements[0]

    if not status.hasDateOrTime:
        raise ValueError("could not parse time")

    if begin not in (0, 1) and end != len(text):
        raise ValueError("could not parse time")

    if not status.hasTime:
        dt = dt.replace(
            hour=now.hour,
            minute=now.minute,
            second=now.second,
            microsecond=now.microsecond
        )

    if status.accuracy == pdt.pdtContext.ACU_HALFDAY:
        dt = dt.replace(day=now.day + 1)

    if begin in (0, 1):
        if begin == 1:
            if text[0] != "\"":
                raise ValueError("could not parse time")

            if not (end < len(text) and text[end] == "\""):
                raise ValueError("could not parse time")

            remaining = text[end + 1:].lstrip(" ,.!")

        else:
            remaining = text[end:].lstrip(" ,.!")

    elif len(text) == end:
        remaining = text[:begin].strip()

    return dt, remaining
