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
import importlib
import math
import random
from functools import partial
from sqlite3 import Row

import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context

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

        self.module = None

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

    @commands.command(aliases=["level"])
    async def rank(self, ctx: Context, *, user: utils.RankedUser = None):
        """Shows a user's rank information."""
        user = user or await utils.RankedUser.convert(ctx, str(ctx.author.id))

        all_users = await self.bot.db.fetchall("SELECT * FROM levels ORDER BY xp DESC")

        levelup_xp = self.get_levelup_xp(user.level)
        level_progress = math.floor(user.level_xp / levelup_xp * 100)

        min_messages = math.ceil((levelup_xp - user.level_xp) / 25)
        max_messages = math.ceil((levelup_xp - user.level_xp) / 15)

        if min_messages == max_messages:
            if min_messages == 1:
                messages_to_levelup = "1 message"
            else:
                messages_to_levelup = f"{min_messages} messages"
        else:
            messages_to_levelup = f"{min_messages} to {max_messages} messages"

        pronoun = "You" if user == ctx.author else "They"

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=f"Rank - {user}", icon_url=ctx.me.avatar.url)
        embed.set_footer(
            text=f"{pronoun} need to send {messages_to_levelup} to level up."
        )
        embed.set_thumbnail(url=user.full.avatar.url)

        embed.add_field(name="Rank", value=f"#{user.position} / {len(all_users)}", inline=False)
        embed.add_field(
            name="Level",
            value=f"{user.level}\n(Level progress: {level_progress}%)",
            inline=False
        )
        embed.add_field(
            name="XP",
            value=f"{user.level_xp} / {levelup_xp} XP\n(Total: {user.xp} XP)",
            inline=False
        )

        await ctx.send(embed=embed)

    @commands.command(aliases=["leaderboard", "lb"])
    async def levels(self, ctx: Context):
        """Sends a link to the leaderboard."""
        await ctx.send("https://leaderboard.veeps.moe")

    @commands.command()
    @commands.is_owner()
    async def rankcard(self, ctx: Context, user: utils.RankedUser = None):
        """Development command for rank cards."""
        user = user or await utils.RankedUser.convert(ctx, str(ctx.author.id))

        if self.module is None:
            self.module = importlib.import_module(".utils.generate")
        else:
            self.module = importlib.reload(self.module)

        await self.bot.loop.run_in_executor(None, partial(self.module.generate, ctx, user))


def setup(bot: utils.Bot):
    bot.add_cog(Levels(bot))
