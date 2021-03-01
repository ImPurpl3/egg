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
import asyncio
import html
import imghdr
import json
import random
import re
import sys
import textwrap
import time
from datetime import datetime, timedelta
from io import BytesIO
from typing import Type
from urllib import parse

import aiohttp
import discord
import parsedatetime as pdt
from discord.ext import commands
from discord.ext.commands import BadArgument, Cog, CommandError, Context
from discord.utils import escape_markdown, sleep_until
from PIL import Image, ImageDraw, ImageFont

from .events import display_error
from .utils import utils

EGG_COLOR = 0xF6DECF

HEX_REGEX = re.compile(r"^#?([a-f0-9]{6}|[a-f0-9]{3})$", re.IGNORECASE)
RGB_REGEX = re.compile(r"^(?:rgb\()?((?:[0-9]{1,3}(?:,\s*|\s+)){2}[0-9]{1,3})\)?$", re.IGNORECASE)
CMYK_REGEX = re.compile(
    r"^(?:cmyk\()?((?:[0-9]{1,3}%?(?:,\s*|\s+)){3}[0-9]{1,3}%?)\)?$", re.IGNORECASE
)

REPO = "https://github.com/ValkyriaKing711/egg/"


class Misc(Cog):
    """A cog containing miscellaneous commands."""
    def __init__(self, bot: utils.Bot):
        self.bot = bot

        with open("./assets/json/colors_lower.json", "r", encoding="utf-8") as f:
            self.colors = json.load(f)

    @commands.command()
    async def nether(self, ctx: Context, *, query: str):
        """Gets an image from https://ceapa.cool/nether."""
        async with ctx.typing():
            quoted = parse.quote(query)
            async with self.bot.session.get(f"https://ceapa.cool/nether/?obj={quoted}") as resp:
                image = await resp.read()
                ext = imghdr.what(None, h=image)
                if not ext:
                    embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                    embed.set_author(name="No images found.", icon_url=ctx.me.avatar_url)
                    return await ctx.send(embed=embed)

                ext = ext.lower().replace("jpeg", "jpg")
                await ctx.send(
                    file=discord.File(
                        BytesIO(image),
                        filename=f"nether_{query.replace(' ', '_')}.{ext}"
                    )
                )

    @commands.command()
    async def melon(self, ctx: Context, *, query: str):
        """Gets an image from https://ceapa.cool/melon."""
        async with ctx.typing():
            quoted = parse.quote(query)
            async with self.bot.session.get(f"https://ceapa.cool/melon/?txt={quoted}") as resp:
                image = await resp.read()
                ext = imghdr.what(None, h=image).lower().replace("jpeg", "jpg")
                await ctx.send(
                    file=discord.File(
                        BytesIO(image),
                        filename=f"melon_{query.replace(' ', '_')}.{ext}"
                    )
                )

    @commands.command()
    async def cumrat(self, ctx: Context, *, text: str):
        """Makes a "Cum rat says:" image."""
        if len(text) > 100:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(
                name="Text must be 100 characters or less.",
                icon_url=ctx.me.avatar_url
            )
            return await ctx.send(embed=embed)

        async with ctx.typing():
            image = await self.bot.loop.run_in_executor(None, self.create_cumrat, text)
            await ctx.send(file=discord.File(image, filename=f"cumrat.png"))

    @staticmethod
    def create_cumrat(text: str):
        """Takes the provided text and applies it onto the cum rat template."""
        text = textwrap.fill(re.sub(r"[^\w\s]+", "", text), 25, break_long_words=True)
        font = ImageFont.truetype("./assets/fonts/angeltears.ttf", size=150)

        image = Image.open("./assets/images/cumrat.png")
        draw = ImageDraw.Draw(image)
        buffer = BytesIO()

        draw.multiline_text((50, 175), text, fill="#000F55", font=font, spacing=0)

        image.save(buffer, "png")
        buffer.seek(0)

        return buffer

    @commands.command()
    async def roblox(self, ctx: Context):
        """Shows how many members are playing Roblox."""
        players = []
        desc = []

        for member in ctx.guild.members:
            if member.activity and member.activity.name:
                if member.activity.name.lower().startswith("roblox"):
                    players.append(str(member))

        amount = len(players)

        for _ in range(10):
            try:
                player = players.pop(0)
                desc.append(player)
            except IndexError:
                break

        if players:
            desc.append(f"...and {len(players)} more \N{FLUSHED FACE}")

        embed = discord.Embed(
            description="\n".join(desc),
            color=EGG_COLOR,
            timestamp=ctx.message.created_at
        )
        embed.set_author(
            name=f"{amount} {utils.plural('member', amount)} "
                 f"{'are' if amount != 1 else 'is'} currently playing Roblox.",
            icon_url=ctx.me.avatar_url
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=["ud", "urbandictionary", "urb"])
    async def urban(self, ctx, term: str, *, index: str = None):
        """Gets a definition from Urban Dicrionary."""
        if index is None:
            index = 0
        else:
            maybe_index = index.split()[-1]
            if maybe_index.isdigit():
                if int(maybe_index) < 1:
                    embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                    embed.set_author(name="Invalid index.", icon_url=ctx.me.avatar_url)
                    await ctx.send(embed=embed)
                else:
                    term += f" {' '.join(index.split()[:-1])}"
                    index = int(maybe_index) - 1
            else:
                term += f" {index}"
                index = 0

        async with aiohttp.ClientSession() as session:
            url = f"http://api.urbandictionary.com/v0/define?term={html.escape(term)}"
            async with session.get(url.replace(" ", "%20")) as response:
                resp = await response.json()

        try:
            item = resp["list"][index]
        except IndexError:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="No definitions found.", icon_url=ctx.me.avatar_url)
            return await ctx.send(embed=embed)

        def convert_to_url(match):
            term = match.group(0).strip('[]')
            url = f"https://www.urbandictionary.com/define.php?term={term}".replace(" ", "%20")
            return f"[{match.group(0).strip('[]')}]({url})"

        definition = re.sub(r"\[[^\]]*\]", convert_to_url, item["definition"])
        example = re.sub(r"\[[^\]]*\]", convert_to_url, item["example"])
        written_on = datetime.strptime(item["written_on"][:10], "%Y-%m-%d").strftime("%B %d, %Y")

        embed = discord.Embed(
            title=f"**__{item['word']}__**",
            description=f"{definition}\n\n_{example}_",
            color=EGG_COLOR,
            url=item["permalink"]
        )
        embed.set_author(
            name="Urban Dictionary",
            icon_url=ctx.me.avatar_url,
            url="https://www.urbandictionary.com/"
        )
        embed.set_footer(
            text=f"\N{SPEAKING HEAD IN SILHOUETTE}: {item['author']} | "
                 f"\N{THUMBS UP SIGN}/\N{THUMBS DOWN SIGN}: "
                 f"{item['thumbs_up']}/{item['thumbs_down']} | {written_on}"
        )

        try:
            await ctx.send(embed=embed)
        except discord.HTTPException:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Definition over 2048 characters.", icon_url=ctx.me.avatar_url)
            embed.add_field(name="Link to definition", value=item["permalink"])
            await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.check_any(
        commands.check(lambda ctx: ctx.channel.id == 527938405951078407),
        commands.has_any_role("@moderator", "@admin", "@owner")
    )
    async def main2(self, ctx: Context):
        """Gives a role with permissions to send messages in Main 2.
           The role is automatically removed after 10 minutes of inactivity in the channel.
        """
        if await self.bot.db.fetchone("SELECT * FROM main2_blacklist WHERE id = ?", ctx.author.id):
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(
                name="You're blacklisted from this command.",
                icon_url=ctx.me.avatar_url
            )
            return await ctx.send(embed=embed)

        role = ctx.guild.get_role(723223787130191953)

        if role in ctx.author.roles:
            return
        
        embed = discord.Embed(
            description="You can now send messages in <#704713087772524565>.",
            color=EGG_COLOR,
            timestamp=ctx.message.created_at
        )
        embed.set_author(name="Role added.", icon_url=ctx.me.avatar_url)

        await ctx.author.add_roles(role)
        await ctx.send(embed=embed)

        def message_check(message: discord.Message):
            return message.author == ctx.author and message.channel.id == 704713087772524565

        def role_check(before: discord.Member, after: discord.Member):
            return role in before.roles and role not in after.roles

        while True:
            futures = [
                self.bot.wait_for(
                    "message",
                    check=message_check
                ),
                self.bot.wait_for(
                    "member_update",
                    check=role_check
                )
            ]
            done, pending = await asyncio.wait(
                futures,
                timeout=600.0,
                return_when=asyncio.FIRST_COMPLETED
            )

            for future in pending:
                future.cancel()

            if not done:
                break

            result = done.pop().result()
            if isinstance(result, discord.Message):
                continue

            break

        await ctx.author.remove_roles(role)

    @main2.command()
    @commands.has_any_role("@moderator", "@admin", "@owner")
    async def block(self, ctx: Context, *, member: discord.Member):
        if role := discord.utils.get(member.roles, name="Main 2"):
            await member.remove_roles(role)

        _id = member.id
        await self.bot.db.execute("INSERT OR IGNORE INTO main2_blacklist (id) VALUES (?)", _id)

        await ctx.message.add_reaction("\N{FLUSHED FACE}")

    @main2.command()
    @commands.has_any_role("@moderator", "@admin", "@owner")
    async def unblock(self, ctx: Context, *, member: discord.Member):
        _id = member.id
        await self.bot.db.execute("DELETE FROM main2_blacklist WHERE id = ?", _id)

        await ctx.message.add_reaction("\N{EGG}")

    @commands.command()
    async def florida(self, ctx: Context):
        async with self.bot.session.get("https://ceapa.cool/florida/api.php") as resp:
            data = await resp.json()

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=data["text"], icon_url=ctx.me.avatar_url)
        embed.set_image(url=data["image"])

        await ctx.send(embed=embed)

    @commands.command()
    async def parsetime(self, ctx: Context, *, date_string: str):
        """Experimental thing, useless for non-testing purposes"""
        calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)
        now = datetime.utcnow() + timedelta(hours=3)
        fmt = "%A, %b %d %Y, %H:%M"
        remaining = "None"

        async def invalid_input():
            embed = discord.Embed(color=EGG_COLOR)
            embed.set_author(name="Time parser", icon_url=ctx.me.avatar_url)

            embed.add_field(name="Source date", value=now.strftime(fmt), inline=False)
            embed.add_field(name="Parsed date", value="?", inline=False)
            embed.add_field(name="Remaining text", value=date_string, inline=False)

            await ctx.send(embed=embed)

        if date_string.endswith("from now"):
            date_string = date_string[:-8].strip()

        elements = calendar.nlp(date_string, sourceTime=now)
        if elements is None or len(elements) == 0:
            return await invalid_input()

        dt, status, begin, end, dt_string = elements[0]

        if not status.hasDateOrTime:
            return await invalid_input()

        if begin not in (0, 1) and end != len(date_string):
            return await invalid_input()

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
                if date_string[0] != "\"":
                    return await invalid_input()

                if not (end < len(date_string) and date_string[end] == "\""):
                    return await invalid_input()

                remaining = date_string[end + 1:].lstrip(" ,.!")

            else:
                remaining = date_string[end:].lstrip(" ,.!")

        elif len(date_string) == end:
            remaining = date_string[:begin].strip()

        embed = discord.Embed(color=EGG_COLOR)
        embed.set_author(name="Time parser", icon_url=ctx.me.avatar_url)

        embed.add_field(name="Source date", value=now.strftime(fmt), inline=False)
        embed.add_field(name="Parsed date", value=dt.strftime(fmt), inline=False)
        embed.add_field(name="Remaining text", value=remaining or "None", inline=False)

        await ctx.send(embed=embed)

    async def get_color_by_name(self, ctx: Context, name: str, word: str):
        name = name.strip("'\"")
        if name.lower() not in self.colors:
            return await self.invalid_color(ctx, word)

        value = self.colors[name]

        data = await self.fetch_color(value.strip("#"), "hex")

        buffer = await self.bot.loop.run_in_executor(None, self.render_color, data["hex"]["value"])
        image = discord.File(buffer, f"{data['hex']['clean']}.png")

        embed = discord.Embed(
            color=discord.Color(int(data["hex"]["clean"], 16)),
            timestamp=ctx.message.created_at
        )


        if name.lower() == data["name"]["value"].lower():
            name = data["name"]["value"]
        else:
            name = name.title()

        embed.set_author(
            name=f"{word.title()} info - {name}",
            icon_url=ctx.me.avatar_url,
            url="https://www.thecolorapi.com"
        )

        embed.set_thumbnail(url=f"attachment://{data['hex']['clean']}.png")

        embed.add_field(name="Hex", value=value, inline=False)
        embed.add_field(name="RGB", value=data["rgb"]["value"], inline=False)
        embed.add_field(name="HSL", value=data["hsl"]["value"], inline=False)
        embed.add_field(name="HSV", value=data["hsv"]["value"], inline=False)
        embed.add_field(name="CMYK", value=data["cmyk"]["value"], inline=False)

        await ctx.send(embed=embed, file=image)

    async def fetch_color(self, value: str, color_format: str):
        url = f"http://thecolorapi.com/id/?{color_format}={value}"
        async with self.bot.session.get(url) as resp:
            return await resp.json()

    @staticmethod
    async def invalid_color(ctx: Context, word: str):
        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=f"Invalid {word}.", icon_url=ctx.me.avatar_url)
        return await ctx.send(embed=embed)

    @staticmethod
    def render_color(color: str):
        image = Image.new("RGB", (128, 128), color=color)
        buffer = BytesIO()

        image.save(buffer, "png")
        buffer.seek(0)

        return buffer

    @commands.command(aliases=["colour"])
    async def color(self, ctx: Context, *, value: str = None):
        """Gets information about a color.

        Accepted formats:
        -  #AABBCC / #ABC / AABBCC / ABC (hex)
        -  246, 222, 207 / 246 222 207 / 246,222,207 / rgb(246, 222, 207) (RGB)
        -  0, 10, 16, 4 / 0 10 16 4 / 0,10,16,4 / cmyk(0, 10, 16, 4) (CMYK, % after values is supported)

        You can also provide a color name:
        -  egg color blue
        -  egg color neon grey
        -  egg color sasquatch socks

        If no value is given, it's chosen randomly.
        """
        word = ctx.invoked_with

        if not value:
            final_value = f"{random.randint(0, 255)}," \
                          f"{random.randint(0, 255)}," \
                          f"{random.randint(0, 255)}"
            color_format = "rgb"

        else:
            try:
                role = await commands.RoleConverter().convert(ctx, value)
                value = f"#{role.color.value:X}"
            except commands.BadArgument:
                pass

            is_hex = bool(re.fullmatch(HEX_REGEX, value))
            is_rgb = bool(re.fullmatch(RGB_REGEX, value))
            is_cmyk = bool(re.fullmatch(CMYK_REGEX, value))

            if sum([is_hex, is_rgb, is_cmyk]) > 1:
                embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                embed.set_author(name="Parsing error.", icon_url=ctx.me.avatar_url)
                return await ctx.send(embed=embed)

            if is_hex:
                final_value = re.fullmatch(HEX_REGEX, value).groups(1)[0]
                color_format = "hex"

            elif is_rgb:
                value = re.fullmatch(RGB_REGEX, value).groups(1)[0]
                final_value = value.replace(" ", ",").replace(",,", ",")

                try:
                    if any(int(i) < 0 or int(i) > 255 for i in final_value.split(",")):
                        return await self.invalid_color(ctx, word)
                except ValueError:
                    return await self.invalid_color(ctx, word)

                color_format = "rgb"

            elif is_cmyk:
                value = re.fullmatch(RGB_REGEX, value).groups(1)[0]
                final_value = value.replace(" ", ",").replace(",,", ",").replace("%", "")

                try:
                    if any(int(i) < 0 or int(i) > 100 for i in final_value.split(",")):
                        return await self.invalid_color(ctx, word)
                except ValueError:
                    return await self.invalid_color(ctx, word)

                color_format = "cmyk"

            else:
                return await self.get_color_by_name(ctx, value, word)

        data = await self.fetch_color(final_value, color_format)

        if "NaN" in data["cmyk"]["value"]:
            return await self.invalid_color(ctx, word)

        buffer = await self.bot.loop.run_in_executor(None, self.render_color, data["hex"]["value"])
        image = discord.File(buffer, f"{data['hex']['clean']}.png")

        embed = discord.Embed(
            color=discord.Color(int(data["hex"]["clean"], 16)),
            timestamp=ctx.message.created_at
        )

        embed.set_author(
            name=f"{word.title()} info - {data[color_format]['value']}",
            icon_url=ctx.me.avatar_url,
            url="https://www.thecolorapi.com"
        )

        embed.set_thumbnail(url=f"attachment://{data['hex']['clean']}.png")

        named_or_nearest = "Name" if data["name"]["exact_match_name"] else f"Approximate name"
        name = data["name"]["value"]

        if not data["name"]["exact_match_name"]:
            name += f" (exact value: {data['name']['closest_named_hex']})"

        embed.add_field(name=named_or_nearest, value=name, inline=False)

        if color_format != "hex":
            embed.add_field(name="Hex", value=data["hex"]["value"], inline=False)
        if color_format != "rgb":
            embed.add_field(name="RGB", value=data["rgb"]["value"], inline=False)

        embed.add_field(name="HSL", value=data["hsl"]["value"], inline=False)
        embed.add_field(name="HSV", value=data["hsv"]["value"], inline=False)

        if color_format != "cmyk":
            embed.add_field(name="CMYK", value=data["cmyk"]["value"], inline=False)

        await ctx.send(embed=embed, file=image)

    @commands.command()
    async def ping(self, ctx: Context):
        """Measures the bot's ping."""
        api_latency = round(self.bot.latency * 1000)

        typing_start = time.monotonic()
        await ctx.trigger_typing()
        typing_end = time.monotonic()

        typing = round((typing_end - typing_start) * 1000)

        site_start = time.monotonic()
        response = await self.bot.session.get("https://discord.com")
        site_end = time.monotonic()

        if 300 >= response.status >= 200:
            site = f"{round((site_end - site_start) * 1000)}"
        else:
            site = "N/A ({response.status} {response.reason})"

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Pong!", icon_url=ctx.me.avatar_url)

        embed.add_field(name="API heartbeat latency", value=f"{api_latency} ms")
        embed.add_field(name="Real latency (typing)", value=f"{typing} ms")
        embed.add_field(name="discord.com", value=f"{site} ms")

        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.has_any_role("@moderator", "@admin", "@owner")
    async def ban(self, ctx: Context, *, user: utils.GuaranteedUser):
        if isinstance(user, discord.Member):
            if any(i in [r.id for r in user.roles] for i in (527939593128116232, 701823598360264774, 527939296829898753)):
                embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                embed.set_author(name="I can't ban this member.", icon_url=ctx.me.avatar_url)
                return await ctx.send(embed=embed)

        try:
            await ctx.guild.ban(user, delete_message_days=7)
        except discord.Forbidden:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="I can't ban this member.", icon_url=ctx.me.avatar_url)
            return await ctx.send(embed=embed)

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=f"Banned {user}.", icon_url=ctx.me.avatar_url)
        embed.add_field(name="Moderator", value=f"{ctx.author.mention} ({ctx.author})")
        await ctx.send(embed=embed)
        await self.bot.get_channel(662441356198674452).send(embed=embed)

    @ban.command()
    @commands.has_any_role("@moderator", "@admin", "@owner")
    async def save(self, ctx: Context, *, user: utils.GuaranteedUser):
        if isinstance(user, discord.Member):
            if any(i in [r.id for r in user.roles] for i in (527939593128116232, 701823598360264774, 527939296829898753)):
                embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                embed.set_author(name="I can't ban this member.", icon_url=ctx.me.avatar_url)
                return await ctx.send(embed=embed)

        try:
            await ctx.guild.ban(user, delete_message_days=0)
        except discord.Forbidden:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="I can't ban this member.", icon_url=ctx.me.avatar_url)
            return await ctx.send(embed=embed)

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=f"Banned {user}.", icon_url=ctx.me.avatar_url)
        embed.add_field(name="Moderator", value=f"{ctx.author.mention} ({ctx.author})")
        await ctx.send(embed=embed)
        await self.bot.get_channel(662441356198674452).send(embed=embed)

    @commands.command()
    @commands.has_any_role(788054854568247328, 527939969059389441)
    @commands.check(lambda ctx: ctx.channel.id == 788047987665272843)
    async def trustedcolor(self, ctx: Context):
        no_color = ctx.guild.get_role(527939969059389441)
        color = ctx.guild.get_role(788054854568247328)

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Trusted color toggled.", icon_url=ctx.author.avatar_url)

        if no_color in ctx.author.roles:
            embed.add_field(name="State", value="On")
            await ctx.author.add_roles(color)
            await ctx.author.remove_roles(no_color)
        else:
            embed.add_field(name="State", value="Off")
            await ctx.author.add_roles(no_color)
            await ctx.author.remove_roles(color)

        await ctx.send(embed=embed)

    @commands.command()
    async def info(self, ctx: Context):
        embed = utils.BaseEmbed(ctx)
        embed.set_author(name="Bot information", icon_url=ctx.me.avatar_url)

        py_version = ".".join(str(i) for i in sys.version_info[:3])
        embed.add_field(name="Python version", value=py_version, inline=False)

        embed.add_field(name="discord.py version", value=discord.__version__, inline=False)
        embed.add_field(name="Source", value=f"[Click here]({REPO} \"bad code alert\")", inline=False)

        vp = self.bot.get_user(self.bot.owner_id)
        embed.set_footer(text=f"made for this server with cum, tears and love by {str(vp)}", icon_url=vp.avatar_url)

        await ctx.send(embed=embed)

    @commands.command(aliases=["inspiro"])
    async def inspirobot(self, ctx: Context):
        """Sends an Inspirobot quote."""
        async with self.bot.session.get(
            "http://inspirobot.me/api?generate=true"
        ) as resp:
            url = await resp.text()
        
        embed = utils.BaseEmbed(ctx)
        embed.set_author(
            name="inspirobot.me",
            url="http://inspirobot.me/",
            icon_url="https://i.imgur.com/UgKWIaF.png"
        )
        embed.set_image(url=url)

        await ctx.send(embed=embed)

    @commands.command(aliases=["mc"])
    async def minecraft(self, ctx: Context):
        """Shows the official Ceapa Cool minecraft server status"""
        async with self.bot.session.get(
            "https://api.mcsrvstat.us/2/minecraft.ceapa.cool"
        ) as resp:
            data = await resp.json()

        online = data["online"]

        embed = utils.BaseEmbed(ctx)
        embed.set_author(
            name="Minecraft Server",
            icon_url=ctx.me.avatar_url
        )
        embed.add_field(name="Connect", value="minecraft.ceapa.cool", inline=False)
        embed.add_field(name="Status", value="Online" if online else "Offline")

        if online:
            version = data["version"]
            embed.add_field(name="Version", value=version)

            players = data["players"]
            names = [escape_markdown(name) for name in players["list"]]

            pl_online = players["online"]
            pl_max = players["max"]
            embed.add_field(name="Slots", value=f"{pl_online}/{pl_max}")

            players_formatted = "\n".join(names) if len(names) <= 10 else \
                "\n".join(names[:10]) + f"\n*and {len(names) - 10} more players*"
            
            embed.add_field(name="Players", value=players_formatted, inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def selfmute(self, ctx: Context, *, args: utils.parse_time):
        """Mutes you for the given time and reason.
           Use at your own risk as admins won't remove your mute.
           If you give a date and/or time, make sure to convert to UTC before.

           Examples:
           -  egg selfmute 8 hours sleep
           -  egg selfmute homework 45 minutes
        """
        until, reason = args
        now = datetime.utcnow()
        delta = utils.format_seconds((until - now).total_seconds())

        reason = reason or None

        muted_role = ctx.guild.get_role(662089736239972373)

        embed = utils.BaseEmbed(ctx)
        embed.set_author(
            name=f"Muted {ctx.author} for {delta}.",
            icon_url=ctx.author.avatar_url
        )
        embed.add_field(name="Reason", value=reason)

        await ctx.send(embed=embed)
        await ctx.author.add_roles(muted_role)

        await sleep_until(until)

        await ctx.send(
            f"Unmuted {ctx.author.mention}.\nSelfmute reason: {reason}"
        )
        await ctx.author.remove_roles(muted_role)

    @selfmute.error
    async def invalid_input(self, ctx: Context, error: Type[CommandError]):
        if isinstance(error, BadArgument) \
        and isinstance(error.original, ValueError):
            embed = utils.BaseEmbed(
                ctx,
                description="Check for typos and make sure you're"
                            "giving a valid time, for example 1 hour,"
                            "2 hours or 2h."
            )
            embed.set_author(name="Could not parse time.")

            await ctx.send(embed=embed)

        else:
            await display_error(ctx, error)

def setup(bot: utils.Bot):
    """Entry point for bot.load_extension."""
    bot.add_cog(Misc(bot))
