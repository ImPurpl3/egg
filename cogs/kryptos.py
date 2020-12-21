"""Extension containing the !Krypt0s cog and helper functions."""
# pylint: disable=invalid-name
import binascii
import imghdr
import re
import string
from base64 import b32decode, b64encode, b64decode
from collections import deque
from io import StringIO

import discord
from discord.ext import commands

from .utils import utils

EGG_COLOR = 0xF6DECF
URL_REGEX = re.compile(r"https?:\/\/(?:www\.)?.+")
ESCAPE_REGEX = re.compile(r'\\x[0123456789abcdef]{2,4}')


def rot_x(x: int, text: str):
    """Rotates alphabets in provided text by x places."""
    alpha = list(string.ascii_lowercase)
    num = [str(i) for i in range(10)]
    rot_alpha = deque(alpha)
    rot_alpha.rotate(-x)
    rot_num = deque(num)
    rot_num.rotate(-x)

    ret = ""
    for char in text.lower():
        if char not in alpha + num:
            ret += char
        else:
            if char.isalpha():
                ret += rot_alpha[alpha.index(char)]
            else:
                ret += rot_num[num.index(char)]

    return ret


def to_atbash(text: str):
    """Applies the atbash cipher on provided text."""
    lowercase = dict(zip(string.ascii_lowercase, string.ascii_lowercase[::-1]))
    uppercase = dict(zip(string.ascii_uppercase, string.ascii_uppercase[::-1]))

    output = ""

    for char in text:
        if not char.isalpha():
            output += char
        elif char.islower():
            output += lowercase[char]
        else:
            output += uppercase[char]

    return output


def text_to_bin(text):
    """Converts text to binary."""
    return bin(int.from_bytes(text.encode(), "big"))


def bin_to_text(binary):
    """Converts binary to ASCII."""
    i = int(binary, 2)
    return i.to_bytes((i.bit_length() + 7) // 8, "big").decode()


class Krypt0s(commands.Cog):
    """A cog containing helper commands for !Krypt0s."""
    def __init__(self, bot: utils.Bot):
        self.bot = bot

    # def cog_check(self, ctx: commands.Context):
    #     return ctx.channel.id == 699042046870290543

    @commands.command(aliases=["mirror"])
    async def atbash(self, ctx: commands.Context, *, text: str):
        """Runs atbash cipher on the provided text."""
        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Atbash cipher", icon_url=ctx.me.avatar_url)
        embed.add_field(name="Input", value=text)
        embed.add_field(name="Output", value=to_atbash(text))

        await ctx.send(embed=embed)

    @commands.command(aliases=["b32"])
    async def base32(self, ctx: commands.Context, *, text: str):
        """Decodes a Base32 string to text."""
        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Base32 -> text", icon_url=ctx.me.avatar_url)
        embed.add_field(name="Input", value=text)
        try:
            embed.add_field(name="Output", value=b32decode(text).decode("utf-8"))
        except binascii.Error:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Invalid Base32 input.", icon_url=ctx.me.avatar_url)

        await ctx.send(embed=embed)

    @commands.command(aliases=["b64"])
    async def base64(self, ctx: commands.Context, *, text: str):
        """Decodes a Base64 string to text."""
        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Base64 -> text", icon_url=ctx.me.avatar_url)
        embed.add_field(name="Input", value=text)
        try:
            embed.add_field(name="Output", value=b64decode(text).decode("utf-8"))
        except binascii.Error:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Invalid Base64 input.", icon_url=ctx.me.avatar_url)

        await ctx.send(embed=embed)

    @commands.command(aliases=["b64encode"])
    async def base64encode(self, ctx: commands.Context, *, text: str):
        """Encodes text to Base64."""
        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Text -> Base64", icon_url=ctx.me.avatar_url)
        embed.add_field(name="Input", value=text)
        embed.add_field(
            name="Output",
            value=b64encode(bytes(text, encoding="utf-8")).decode("utf-8")
        )

        await ctx.send(embed=embed)

    @commands.command(name="hex", aliases=["hextotext", "htt", "base16", "b16"])
    async def _hex(self, ctx: commands.Context, *, hex_string: str):
        """Decodes a hexadecimal value to ASCII."""
        spaces_removed = hex_string.replace(" ", "").upper()
        cleaned = " ".join(spaces_removed[i:i + 2] for i in range(0, len(spaces_removed), 2))

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Hexadecimal -> text", icon_url=ctx.me.avatar_url)
        embed.add_field(name="Input", value=cleaned)
        try:
            embed.add_field(name="Output", value=bytearray.fromhex(hex_string).decode())
        except ValueError as e:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(
                name=f"Non-hexadecimal number found at position {int(e.args[0].split()[-1]) + 1}.",
                icon_url=ctx.me.avatar_url
            )

        await ctx.send(embed=embed)

    @commands.command()
    async def imgtxt(self, ctx: commands.Context, url: str = None):
        """Strips image bytes from all non-ASCII characters."""
        if url is None and not ctx.message.attachments:
            embed = discord.Embed(
                description="Either use ``egg imgtxt image_url`` or send only " \
                            "``egg imgtxt`` with an image attached to the message.",
                color=EGG_COLOR,
                timestamp=ctx.message.created_at
            )
            embed.set_author(name="Missing image.", icon_url=ctx.me.avatar_url)
            return await ctx.send(embed=embed)

        if ctx.message.attachments:
            b = await ctx.message.attachments[0].read()
            filename = ctx.message.attachments[0].filename

            if imghdr.what(None, h=b) is None:
                embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                embed.set_author(name="Invalid image format.", icon_url=ctx.me.avatar_url)
                return await ctx.send(embed=embed)

        elif url is not None:
            async with self.bot.session.get(str(url)) as resp:
                if not resp.content_type.startswith("image"):
                    embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                    embed.set_author(
                        name="Supplied URL is not an image.",
                        icon_url=ctx.me.avatar_url
                    )
                    return await ctx.send(embed=embed)

                b = await resp.read()

            filename = "image"

        bytes_str = str(b)
        escaped = ESCAPE_REGEX.sub("", bytes_str)
        to_send = StringIO("\r\n".join(escaped.split(r"\r\n")).strip("b'\""))

        await ctx.send(file=discord.File(to_send, filename=f"{filename}.txt"))

    @commands.command(aliases=["caesar"])
    async def rot(self, ctx: commands.Context, x: commands.Greedy[int], *, text: str):
        """Runs a ROT cipher on the provided text."""
        if not x:
            s = f"[Input]\n{text}\n\n"
            s += "\n\n".join(f"[ROT-{i}]\n{rot_x(i, text)}" for i in range(1, 26))
            return await ctx.send(file=discord.File(StringIO(s), filename="rot1-25.txt"))

        if len(x) > 1:
            text = " ".join(x[1:] + text.split())

        x = x[0]

        while x >= 26:
            x -= 26

        rotated = rot_x(x, text)
        case_matched = "".join(char.upper() \
                                if text[i].isupper() \
                                else char \
                                for i, char in enumerate(rotated))

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=f"ROT-{x}", icon_url=ctx.me.avatar_url)
        embed.add_field(name="Input", value=text)
        embed.add_field(name="Output", value=case_matched)

        await ctx.send(embed=embed)

    @commands.command()
    async def binary(self, ctx: commands.Context, *, original_data: str):
        """Decodes a binary value into ASCII."""
        data = original_data.replace(" ", "")
        if any(char not in ["0", "1"] for char in set(data)):
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Invalid binary input.", icon_url=ctx.me.avatar_url)
            return await ctx.send(embed=embed)

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=f"Binary -> text", icon_url=ctx.me.avatar_url)
        embed.add_field(name="Input", value=original_data)

        try:
            embed.add_field(name="Output", value=bin_to_text(data))
        except UnicodeDecodeError:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Invalid binary input.", icon_url=ctx.me.avatar_url)
            return await ctx.send(embed=embed)

        await ctx.send(embed=embed)


def setup(bot: utils.Bot):
    """Entry point for bot.load_extension."""
    bot.add_cog(Krypt0s(bot))
