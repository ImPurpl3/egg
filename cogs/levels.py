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
import json
import math
import random
from base64 import decodebytes
from io import BytesIO
from sqlite3 import Row

import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context
from PIL import Image, ImageDraw, ImageFont

from .utils import utils

EGG_COLOR = 0xF6DECF

ranks = {
    5: 668535742535958528,
    15: 668536066189426718,
    30: 668536043326144557,
    50: 668536541634887710,
    75: 668536973358661644,
    100: 668537115528921088
}


class Levels(Cog):
    def __init__(self, bot: utils.Bot):
        self.bot = bot
        self.levelup_channel = self.bot.get_channel(668535454580211768)

    @staticmethod
    def get_levelup_xp(level: int):
        return 5 * level**2 + 50*level + 100

    @Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != 527932145273143306:
            return

        data = await self.bot.db.fetchone("SELECT * FROM levels WHERE id = ?", member.id)

        if not data:
            return

        guild = member.guild
        name = str(member)
        avatar_url = str(member.avatar.replace(512, static_format="png"))

        if name != data["last_known_as"] or avatar_url != data["last_known_avatar_url"]:
            await self.bot.db.execute(
                "UPDATE levels SET last_known_as = ?, last_known_avatar_url = ? WHERE id = ?",
                name,
                avatar_url,
                member.id
            )

        if data["level"] >= 5:
            roles = [guild.get_role(r) for (l, r) in ranks.items() if data["level"] > l]
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
            str(message.author.avatar.replace(static_format="png"))
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
            if (role := message.guild.get_role(ranks.get(level))):
                await message.author.add_roles(role)
                await self.levelup_channel.send(
                    f"gg {message.author.mention}, you leveled up to level {level}\n"
                    f"*level reward: {role.name}*"
                )
            else:
                await self.levelup_channel.send(f"gg {message.author.mention}, you leveled up to level {level}")

        await self.bot.db.execute("UPDATE levels SET level = ?, xp = ?, level_xp = ? WHERE id = ?", level, xp, level_xp, message.author.id)

    @Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Called when a user changes their name, discriminator or avatar."""
        if str(before) != str(after):
            await self.bot.db.execute(
                "UPDATE levels SET last_known_as = ? WHERE id = ?",
                str(after),
                after.id
            )
        if str(before.avatar.url) != str(after.avatar.url):
            await self.bot.db.execute(
                "UPDATE levels SET last_known_avatar_url = ? WHERE id = ?",
                str(after.avatar.replace(static_format="png", size=512)),
                after.id
            )

    async def send_rank_data_from_row(self, ctx: Context, row: Row):
        """Sends a user's rank information from a database row.
           Used when a deleted user is returned by utils.RankedUser."""
        all_users = await self.bot.db.fetchall("SELECT * FROM levels ORDER BY xp DESC")

        position = [row["id"] for row in all_users].index(row["id"]) + 1
        level = row["level"]
        level_xp = row["level_xp"]
        levelup_xp = self.get_levelup_xp(level)
        total_xp = row["xp"]

        level_progress = math.floor(level_xp / levelup_xp * 100)
        min_messages = math.ceil((levelup_xp - level_xp) / 25)
        max_messages = math.ceil((levelup_xp - level_xp) / 15)

        if min_messages == max_messages:
            if min_messages == 1:
                messages_to_levelup = "1 message"
            else:
                messages_to_levelup = f"{min_messages} messages"
        else:
            messages_to_levelup = f"{min_messages} to {max_messages} messages"

        name = row['last_known_as']

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=f"Rank - {name} (Deleted)", icon_url=ctx.me.avatar.url)
        embed.set_footer(
            text=f"They need to send {messages_to_levelup} to level up."
        )
        embed.set_thumbnail(url=row["last_known_avatar_url"])

        embed.add_field(name="Rank", value=f"#{position} / {len(all_users)}", inline=False)
        embed.add_field(
            name="Level",
            value=f"{level}\n(Level progress: {level_progress}%)",
            inline=False
        )
        embed.add_field(
            name="XP",
            value=f"{level_xp} / {levelup_xp} XP\n(Total: {total_xp} XP)",
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command(aliases=["level"])
    async def rank(self, ctx: Context, *, member: utils.RankedUser = None):
        """Shows a member's rank information."""
        member = member or ctx.author

        if isinstance(member, Row):
            return await self.send_rank_data_from_row(ctx, member)

        await self.bot.db.execute("INSERT OR IGNORE INTO levels (id) VALUES (?)", member.id)
        all_users = await self.bot.db.fetchall("SELECT * FROM levels ORDER BY xp DESC")
        data = discord.utils.find(lambda row: row["id"] == member.id, all_users)

        position = [row["id"] for row in all_users].index(member.id) + 1
        level = data["level"]
        level_xp = data["level_xp"]
        levelup_xp = self.get_levelup_xp(level)
        total_xp = data["xp"]

        level_progress = math.floor(level_xp / levelup_xp * 100)
        min_messages = math.ceil((levelup_xp - level_xp) / 25)
        max_messages = math.ceil((levelup_xp - level_xp) / 15)

        if min_messages == max_messages:
            if min_messages == 1:
                messages_to_levelup = "1 message"
            else:
                messages_to_levelup = f"{min_messages} messages"
        else:
            messages_to_levelup = f"{min_messages} to {max_messages} messages"

        pronoun = "You" if member == ctx.author else "They"

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=f"Rank - {member}", icon_url=ctx.me.avatar.url)
        embed.set_footer(
            text=f"{pronoun} need to send {messages_to_levelup} to level up."
        )
        embed.set_thumbnail(url=member.avatar.url)

        embed.add_field(name="Rank", value=f"#{position} / {len(all_users)}", inline=False)
        embed.add_field(
            name="Level",
            value=f"{level}\n(Level progress: {level_progress}%)",
            inline=False
        )
        embed.add_field(
            name="XP",
            value=f"{level_xp} / {levelup_xp} XP\n(Total: {total_xp} XP)",
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command(aliases=["leaderboard", "lb"])
    async def levels(self, ctx: Context):
        """Sends a link to the leaderboard."""
        await ctx.send("https://leaderboard.veeps.moe")


def setup(bot: utils.Bot):
    bot.add_cog(Levels(bot))
