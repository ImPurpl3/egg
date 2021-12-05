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
import random
from functools import partial
from io import BytesIO
from math import ceil, floor
from sqlite3 import Row

import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context
from PIL import Image, ImageChops, ImageDraw, ImageFont

from .utils import utils

EGG_COLOR = 0xF6DECF

RANKS = {
    5: 668535742535958528,
    15: 668536066189426718,
    30: 668536043326144557,
    50: 668536541634887710,
    75: 668536973358661644,
    100: 668537115528921088
}

# Constants for rank card generation
REGULAR_FONT = "./assets/fonts/FiraMono-Regular.ttf"
BOLD_FONT = "./assets/fonts/FiraMono-Bold.ttf"

BAR_COLOR = "#0a9500"
GREY = "#808080"
TRANSPARENT = "#00000000"
WHITE = "#FFFFFF"


class Levels(Cog):
    def __init__(self, bot: utils.Bot):
        self.bot = bot
        self.levelup_channel = self.bot.get_channel(668535454580211768)

    @staticmethod
    def get_levelup_xp(level: int):
        return 5 * level**2 + 50*level + 100

    def generate_card(self, user: utils.RankedUser, avatar_bytes: bytes, users: list[Row]):
        im = Image.open("./assets/images/DefaultBg.png").convert("RGBA")
        bar = Image.open("./assets/images/BarPic.png").convert("RGBA")
        out = Image.open("./assets/images/outline.png").convert("RGBA")

        level = user.level
        level_xp = user.level_xp
        levelup_xp = self.get_levelup_xp(level)

        level_prog = level_xp / levelup_xp
        bar_length = floor(552 * level_prog)  # calculate progress bar length, 552 is 100%

        # new layer for the bar fill -> draw the bar at the right position -> merge bar on top
        fill = Image.new("RGBA", im.size, TRANSPARENT)
        ImageDraw.Draw(fill).rectangle((222, 189, 222+bar_length, 245), BAR_COLOR)
        fill.alpha_composite(bar)

        # merge bar on top of the background, and outline on top of those
        im.alpha_composite(fill)
        im.alpha_composite(out)

        avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((215, 215), Image.LANCZOS)

        size = (avatar.size[0] * 5, avatar.size[1] * 5)  # exaggerated size for the circle mask
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0) + size, fill=255)

        # scale circle mask down with lanczos sampling to make it look smoother
        mask = mask.resize(avatar.size, Image.LANCZOS)

        # use mask to crop avatar into a circle
        # darker() ensures all existing transparency in the avatar is left unchanged
        mask = ImageChops.darker(mask, avatar.split()[-1])
        avatar.putalpha(mask)

        # paste avatar on an empty layer
        avy_layer = Image.new("RGBA", im.size, TRANSPARENT)
        avy_layer.paste(avatar, (56, 32))

        # merge avatar on top of everything else (progress bar etc.)
        im.alpha_composite(avy_layer)

        # All text will be drawn on top the current state, no new layers whatsoever
        # Username, full size/bold white font
        size = 60
        n_font = ImageFont.truetype(BOLD_FONT, size)

        # size defaults to 60, decreasing until text is less than 430 pixels wide and at least 23
        while (r_bound := n_font.getbbox(user.full.name, anchor="ls")[2]) > 430 and size >= 23:
            size -= 1
            n_font = ImageFont.truetype(BOLD_FONT, size)

        t_draw = ImageDraw.Draw(im)
        t_draw.text((290, 100), user.full.name, WHITE, n_font, "ls")

        # Discriminator, half size/regular grey font
        d_font = ImageFont.truetype(REGULAR_FONT, size // 2)
        discrim_position = (290 + r_bound + 1, 100)  # right after name, plus 1 pixel to separate
        t_draw.text(discrim_position, f"#{user.full.discriminator}", GREY, d_font, "ls")

        # Stats
        prog_font = ImageFont.truetype(REGULAR_FONT, 30)

        # draw level % in center of bar if it's wide enough, otherwise a bit to its right
        bar_center = (_, center_h) = ((222 + 222+bar_length) // 2, (245 + 189) // 2)
        if level_prog >= 0.25:
            bar_center = (_, center_h) = ((222 + 222+bar_length) // 2, (245 + 189) // 2)
            t_draw.text(bar_center, f"{floor(level_prog * 100)}%", WHITE, prog_font, "mm")
        else:
            # to avoid overlapping, if bar length is less than 5% then pretend it is 5%
            next_to_bar = (222 + max(floor(552 * 0.05), bar_length) + 10, center_h)
            t_draw.text(next_to_bar, f"{floor(level_prog * 100)}%", WHITE, prog_font, "lm")

        col_font = ImageFont.truetype(REGULAR_FONT, 20)

        # Rank and level
        t_draw.multiline_text(
            (297, 115),
            f" Rank: #{user.position}/{len(users)}\nLevel: {level}",
            WHITE,
            col_font,
            "la",
            spacing=8
        )

        # Level XP and total XP
        t_draw.multiline_text(
            (755, 115),
            f"   XP: {level_xp}/{levelup_xp} XP\nTotal: {user.xp} XP",
            WHITE,
            col_font,
            "ra",
            spacing=8
        )

        # Messages needed to level up
        min_messages = ceil((levelup_xp - level_xp) / 25)
        max_messages = ceil((levelup_xp - level_xp) / 15)

        if min_messages == max_messages:
            n_messages = min_messages
            plural = n_messages != 1
        else:
            n_messages = f"{min_messages} - {max_messages}"
            plural = True

        small_font = ImageFont.truetype(REGULAR_FONT, 14)
        t_draw.text(
            (815, 270),
            f"{n_messages} message{'s' if plural else ''} needed to level up",
            WHITE,
            small_font,
            "rd"
        )

        # Return the finished image as .png in a file buffer
        buffer = BytesIO()
        im.save(buffer, "png")
        buffer.seek(0)

        return buffer

    @Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != 527932145273143306:
            return

        data = await self.bot.db.fetchone("SELECT * FROM levels WHERE id = ?", member.id)

        if not data:
            return

        guild = member.guild
        name = str(member)
        avatar_url = str(member.display_avatar.replace(size=512, static_format="png"))

        if name != data["last_known_as"] or avatar_url != data["last_known_avatar_url"]:
            await self.bot.db.execute(
                "UPDATE levels SET last_known_as = ?, last_known_avatar_url = ? WHERE id = ?",
                name,
                avatar_url,
                member.id
            )

        if data["level"] >= 5:
            roles = [guild.get_role(r) for (l, r) in RANKS.items() if data["level"] > l]
            await member.add_roles(*roles)

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        is_blacklisted_channel = message.channel.id in [
            527938405951078407,
            662073837017497600,
            664303128027332628,
            662063429879595009
        ]
        is_not_ceapa_cool = not message.guild or message.guild.id != 527932145273143306
        is_not_valid_message = message.author.bot or message.type != discord.MessageType.default

        if is_blacklisted_channel or is_not_ceapa_cool or is_not_valid_message:
            return

        bucket = self.bot.xp_cooldown.get_bucket(message)
        is_on_cooldown = bucket.update_rate_limit()

        if is_on_cooldown:
            return

        await self.bot.db.execute(
            """INSERT OR IGNORE
                   INTO levels (id, last_known_as, last_known_avatar_url)
                       VALUES (?, ?, ?)
            """,
            message.author.id,
            str(message.author),
            str(message.author.display_avatar.replace(static_format="png"))
        )
        data = await self.bot.db.fetchone("SELECT * FROM levels WHERE id = ?", message.author.id)
        level = data["level"]

        xp_to_add = random.SystemRandom().randint(15, 25)
        level_xp = data["level_xp"] + xp_to_add
        xp = data["xp"] + xp_to_add

        levelup_xp = self.get_levelup_xp(level)

        if level_xp >= levelup_xp:
            level += 1
            level_xp = level_xp - levelup_xp
            if (role := message.guild.get_role(RANKS.get(level))):
                await message.author.add_roles(role)
                await self.levelup_channel.send(
                    f"gg {message.author.mention}, you leveled up to level {level}\n"
                    f"*level reward: {role.name}*"
                )
            else:
                await self.levelup_channel.send(
                    f"gg {message.author.mention}, you leveled up to level {level}"
                )

        await self.bot.db.execute(
            "UPDATE levels SET level = ?, xp = ?, level_xp = ? WHERE id = ?",
            level,
            xp,
            level_xp,
            message.author.id
        )

    @Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Called when a user changes their name, discriminator or avatar."""
        if str(before) != str(after):
            await self.bot.db.execute(
                "UPDATE levels SET last_known_as = ? WHERE id = ?",
                str(after),
                after.id
            )
        if str(before.display_avatar.url) != str(after.display_avatar.url):
            await self.bot.db.execute(
                "UPDATE levels SET last_known_avatar_url = ? WHERE id = ?",
                str(after.display_avatar.replace(static_format="png", size=512)),
                after.id
            )

    @commands.command()
    async def rank(self, ctx: Context, *, user: utils.RankedUser = None):
        """Shows a user's rank information."""
        user = user or await utils.RankedUser.convert(ctx, str(ctx.author.id))

        # avatar = await user.full.display_avatar.replace(size=256, format="png").read()
        avatar = await (await self.bot.fetch_user(user.full.id)).avatar.replace(size=256, format="png").read()
        users = await self.bot.db.fetch("SELECT * FROM levels")
        func = partial(self.generate_card, user, avatar, users)

        buffer = await self.bot.loop.run_in_executor(None, func)
        await ctx.send(file=discord.File(buffer, filename="rank.png"))

    @commands.command(aliases=["leaderboard", "lb"])
    async def levels(self, ctx: Context):
        """Sends a link to the leaderboard."""
        await ctx.send("https://leaderboard.veeps.moe")


def setup(bot: utils.Bot):
    bot.add_cog(Levels(bot))
