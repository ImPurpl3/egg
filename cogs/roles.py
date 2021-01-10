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
import re
from textwrap import dedent

from discord import Message, PartialEmoji, RawReactionActionEvent, Role
from discord.ext import commands
from discord.ext.commands import Cog, Context
from discord.utils import find, get
from .utils import utils


class CategoryEntry:
    pattern = re.compile(r"^(<:.+?:\d+>|.):\s*(.+)$")

    def __init__(self, emoji: str, description: str):
        self.description = description
        self.emoji = emoji

    def __eq__(self, other):
        if isinstance(other, CategoryEntry):
            return other.description == self.description and other.emoji == self.emoji
        return False

    def __str__(self) -> str:
        return f"{self.emoji}: {self.description}"

    @classmethod
    def from_string(cls, line: str):
        return cls(*cls.pattern.match(line).groups())


class RoleCategory:
    def __init__(self, message: Message, name: str):
        self.message = message

        self.name = name
        self.entries = []
        self.title = ""

    def parse_lines(self):
        content: str = self.message.content
        lines = [i for i in content.split("\n") if i]

        self.title = lines.pop(0)

        for line in lines:
            self.entries.append(CategoryEntry.from_string(line))

    async def add_entry(self, entry: CategoryEntry):
        content = f"{self.message.content}\n{entry}"
        
        await self.message.edit(content=content)
        await self.message.add_reaction(entry.emoji) 
        self.entries.append(entry)

    async def remove_entry(self, entry: CategoryEntry):
        entry_list = "\n".join(str(i) for i in self.entries)
        content = f"**{self.title}:**\n{entry_list}"

        await self.message.edit(content=content)
        await self.message.clear_reaction(entry.emoji)
        self.entries.remove(entry)


class Roles(Cog):
    def __init__(self, bot: utils.Bot):
        self.bot = bot
        self.channel_id = 797633928152088586

        self.categories = []
        self.role_ids = {}

    async def fetch_categories(self) -> list:
        data = await self.bot.db.fetchall("SELECT * FROM r_categories")
        message_ids = {i["name"]: i["message_id"] for i in data}
        names = {v: k for k, v in message_ids.items()}

        history = self.bot.get_channel(self.channel_id).history(limit=None)
        messages = [message async for message in history if message.id in message_ids.values()]

        return [
            RoleCategory(message, names[message.id])
            for message in messages
        ]

    async def get_category(self, id_or_name: str) -> RoleCategory:
        if not self.categories:
            self.categories = await self.fetch_categories()

        if id_or_name.isdigit():
            for category in self.categories:
                if category.message.id == int(id_or_name):
                    return category
        else:
            for category in self.categories:
                if category.name == id_or_name:
                    return category

    async def get_role_id(self, emoji: PartialEmoji) -> int:
        if not self.role_ids:
            roles = await self.bot.db.fetchall("SELECT * FROM roles")
            self.role_ids = {i["emoji"]: i["role_id"] for i in roles}

        return self.role_ids.get(str(emoji))

    @commands.group(invoke_without_command=True)
    async def roles(self, ctx: Context):
        await ctx.send(f"Moved to <#{self.channel_id}>.")

    @roles.command()
    @commands.has_permissions(administrator=True)
    async def newcategory(self, ctx: Context, name: str, *, title: str):
        channel = self.bot.get_channel(self.channel_id)
        message = await channel.send(f"**{title}:**")

        await self.bot.db.execute(
            "INSERT INTO r_categories (name, message_id) VALUES (?, ?)",
            name, message.id
        )
        self.categories.append(RoleCategory(message, name))

        await ctx.message.add_reaction(get(ctx.guild.emojis, name="cumrat"))

    @roles.command()
    @commands.has_permissions(administrator=True)
    async def new(self, ctx: Context, category: str, role: Role, emoji: str, *, text: str):
        category = await self.get_category(category)
        entry = CategoryEntry(emoji, text)

        await self.bot.db.execute(
            "INSERT INTO roles (emoji, role_id) VALUES (?, ?)",
            emoji, role.id
        )
        await category.add_entry(entry)
        self.role_ids[emoji] = role.id

        await ctx.message.add_reaction(get(ctx.guild.emojis, name="cumrat"))

    @roles.command()
    @commands.has_permissions(administrator=True)
    async def delete(self, ctx: Context, category: str, *, role_identifier: str):
        try:
            role = (await commands.RoleConverter().convert(ctx, role_identifier)).id
        except commands.RoleNotFound:
            role = await self.get_role_id(role_identifier)

        if isinstance(role, int):
            emojis = {v: k for k, v in self.role_ids.items()}
            emoji = emojis[role]
        else:
            emoji = role

        category = await self.get_category(category)
        await category.remove_entry(get(category.entries, emoji=emoji))

        await ctx.message.add_reaction(get(ctx.guild.emojis, name="cumrat"))

    async def handle_reaction(self, payload: RawReactionActionEvent):
        channel_id = payload.channel_id
        guild_id = payload.guild_id
        user_id = payload.user_id

        if channel_id != self.channel_id or user_id == self.bot.user.id:
            return

        emoji = payload.emoji

        if not (role_id := await self.get_role_id(emoji)):
            return

        guild = self.bot.get_guild(guild_id)
        member = guild.get_member(user_id)
        role = guild.get_role(role_id)

        if payload.event_type == "REACTION_ADD" and role not in member.roles:
            await member.add_roles(role)
            return True

        if payload.event_type == "REACTION_REMOVE" and role in member.roles:
            await member.remove_roles(role)
            return False

        return None


    @Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        await self.handle_reaction(payload)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        await self.handle_reaction(payload)


def setup(bot: utils.Bot):
    bot.add_cog(Roles(bot))
