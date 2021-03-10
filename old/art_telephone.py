"""
this module is incredibly rushed and is not representative of my usual
code quality, proceed with caution.

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
from asyncio import TimeoutError
from io import BytesIO
from imghdr import what
from random import SystemRandom

from discord import Emoji, File, Member, Message, Reaction
from discord.ext import commands
from discord.ext.commands import Cog, Context

from .utils import utils

random = SystemRandom()

MESSAGE_TEMPLATE = "hi {}, take a good look at this image and " \
                   "replicate it as best as you can. once you're done, " \
                   "send the image to <#806935123102531584>, make sure " \
                   "it's fine and add <:cumrat:705164503163207692> as a " \
                   "reaction to the confirmation message to confirm.\n" \
                   "if you have any questions, you can use this channel."


class Telephone(Cog):
    def __init__(self, bot: utils.Bot):
        self.bot = bot
        self.start_channel = self.bot.get_channel(808524170254090240)
        self.channel = self.bot.get_channel(806935123102531584)

        self.role = self.channel.guild.get_role(807753537340964925)
        self.current = None if not self.role.members else self.role.members[0]
        self.wait_message = None

        self.members = []

        try:
            with open("tphone_players.json", "r", encoding="utf-8") as file:
                members = json.load(file)
        except FileNotFoundError:
            members = []

        for i in members:
            if member := self.channel.guild.get_member(i):
                self.members.append(member)

    def cog_unload(self):
        with open("tphone_players.json", "w", encoding="utf-8") as file:
            json.dump([i.id for i in self.members], file, indent=4)

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def telephone(self, ctx: Context):
        await ctx.send_help(self.telephone)

    @telephone.command()
    @commands.has_permissions(administrator=True)
    async def loadmembers(self, ctx: Context):
        channel = self.bot.get_channel(662066995205898250)
        message = await channel.fetch_message(804120910562852905)
        self.members = await message.reactions[0].users().flatten()
        await ctx.message.add_reaction(":cumrat:705164503163207692")

    @telephone.command(aliases=["next", "pull"])
    @commands.has_permissions(administrator=True)
    async def draw(self, ctx: Context):
        if self.current:
            await self.current.remove_roles(self.role)
            self.members.append(self.current)
            self.current = None

        if self.wait_message:
            await self.wait_message.delete()

        await self.start_channel.purge(limit=100)

        def pine_send_check(m: Message) -> bool:
            return m.author.id == 295579220657176577 and \
                   m.channel == self.start_channel and m.attachments

        msg = await self.start_channel.send(
            "<@295579220657176577> send pixelated drawing "
            "and add cumrat reaction to confirm"
        )
        resp = await self.bot.wait_for("message", check=pine_send_check)

        def pine_confirm_check(r: Reaction, u: Member) -> bool:
            return isinstance(r.emoji, Emoji) and \
                   r.message.id == resp.id and \
                   r.emoji.name == "cumrat" and u.id == 295579220657176577

        await self.bot.wait_for("reaction_add", check=pine_confirm_check)

        image = BytesIO(await resp.attachments[0].read())
        self.file = (
            image,
            f"pixelated_{resp.id}.{what('', h=image.read()).replace('jpeg', 'jpg')}"
        )

        self.file[0].seek(0)

        await self.start_channel.delete_messages([msg, resp])

        self.current = random.choice(self.members)
        self.members.remove(self.current)
        await self.current.add_roles(self.role)

        self.wait_message = await self.start_channel.send(
            MESSAGE_TEMPLATE.format(self.current.mention),
            file=File(*self.file)
        )

    @telephone.command()
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx: Context, *, member: utils.GuaranteedUser):
        self.members.remove(member)
        await ctx.message.add_reaction(":cumrat:705164503163207692")

    @Cog.listener()
    async def on_message(self, message: Message):
        if message.channel == self.channel and message.author == self.current:
            if not message.attachments:
                return await message.delete()

            msg = await self.start_channel.send(
                "react here with <:cumrat:705164503163207692> to confirm"
            )

            def confirm_check(r: Reaction, u: Member) -> bool:
                return isinstance(r.emoji, Emoji) and \
                       r.emoji.name == "cumrat" and \
                       r.message.id == msg.id and u == self.current
                
            try:
                reaction, _ = await self.bot.wait_for(
                    "reaction_add", check=confirm_check, timeout=60
                )
            except TimeoutError:
                await self.start_channel.send(
                    f"{self.current.mention} send the image again, "
                    "confirmation timed out."
                )
                return await message.delete()

            await reaction.clear()

            await self.current.remove_roles(self.role)
            self.current = None

            if self.wait_message:
                self.wait_message = None
                await self.wait_message.delete()

            await self.start_channel.purge(limit=100)

            if not self.members:
                await message.channel.send("all done")

            def pine_send_check(m: Message) -> bool:
                return m.author.id == 295579220657176577 and \
                       m.channel == self.start_channel and m.attachments

            msg = await self.start_channel.send(
                "<@295579220657176577> send pixelated drawing "
                "and add cumrat reaction to confirm"
            )
            resp = await self.bot.wait_for(
                "message", check=pine_send_check
            )

            def pine_confirm_check(r: Reaction, u: Member) -> bool:
                return isinstance(r.emoji, Emoji) and \
                       r.message.id == resp.id and \
                       r.emoji.name == "cumrat" and u.id == 295579220657176577

            await self.bot.wait_for("reaction_add", check=pine_confirm_check)

            image = BytesIO(await resp.attachments[0].read())
            self.file = (
                image,
                f"pixelated_{resp.id}.{what('', h=image.read()).replace('jpeg', 'jpg')}"
            )

            self.file[0].seek(0)

            await self.start_channel.delete_messages([msg, resp])

            self.current = random.choice(self.members)
            self.members.remove(self.current)
            await self.current.add_roles(self.role)

            self.wait_message = await self.start_channel.send(
                MESSAGE_TEMPLATE.format(self.current.mention),
                file=File(*self.file)
            )


def setup(bot: utils.Bot):
    bot.add_cog(Telephone(bot))
