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
from typing import Union

from discord import PartialEmoji, RawReactionActionEvent, Role
from discord.ext import commands
from discord.ext.commands import Cog, Context

from .utils import utils

SUCCESS_EMOJI = "<:yes:567019270467223572>"


class Roles(Cog):
    def __init__(self, bot: utils.Bot):
        self.bot = bot
        self.channel = bot.get_channel(797633928152088586)
        self.role_dict = {}

        self.bot.loop.create_task(self.cache_roles())

    async def cache_roles(self):
        data = await self.bot.db.fetch("SELECT * FROM roles")
        for i in data:
            self.role_dict[i["emoji"]] = dict(i)

    @commands.group(invoke_without_command=True)
    async def roles(self, ctx: Context):
        """Command group for managing reaction roles and categories."""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("<#797633928152088586>")
        else:
            await ctx.send_help(self.roles)

    @commands.has_permissions(administrator=True)
    @roles.command(name="add", aliases=["new"])
    async def role_add(self, ctx: Context, category_id: int, role: Union[Role, str],
                       emoji: Union[PartialEmoji, PartialEmoji.from_str], *, text: str):
        """Adds a role to the given category.

           <role> can be an existing role name, id or mention;
           or alternatively a name which a new role will be created as.

           As per usual, all arguments except the last one (for example <role>)
           require "quotes" around them if it's multiple words.

           Example usage:
           egg roles add 797953789826302002 "flying disk" 🥏 Gives access to the flying disk channel.
               - In case a role called flying disk doesn't exist, it'll create one on the fly.
        """
        if emoji.id and emoji.id not in [e.id for e in self.bot.emojis]:
            return await ctx.send("A custom emoji can only be added if I'm able to see it.")

        message = await self.channel.fetch_message(category_id)
        text = text.replace("\n", " ")
        new_content = message.content + f"\n{emoji}: {text}"

        if isinstance(role, str):
            role = await ctx.guild.create_role(name=role)

        await self.bot.db.execute(
            "INSERT INTO roles (emoji, role_id, category_id, description) VALUES (?, ?, ?, ?)",
            str(emoji), role.id, category_id, text
        )
        self.role_dict[str(emoji)] = {
            "category_id": category_id,
            "emoji": str(emoji),
            "role_id": role.id,
            "description": text
        }

        await message.edit(content=new_content)
        await message.add_reaction(emoji)

        await ctx.message.add_reaction(SUCCESS_EMOJI)

    @commands.has_permissions(administrator=True)
    @roles.command(name="delete", aliases=["remove"])
    async def role_delete(self, ctx: Context, *,
                          emoji: Union[PartialEmoji, PartialEmoji.from_str]):
        """Deletes a role from its respective category.

           The command's only parameter is the emoji of the role that's being deleted. 

           Example usage:
           egg roles delete 🥏
        """
        role_data = await self.bot.db.fetchone("SELECT * FROM roles WHERE emoji = ?", str(emoji))
        category_id = role_data["category_id"]
        message = await self.channel.fetch_message(category_id)
        
        lines = message.content.split("\n")
        lines.remove(f"{emoji}: {role_data['description']}")

        await self.bot.db.execute("DELETE FROM roles WHERE emoji = ?", str(emoji))
        del self.role_dict[str(emoji)]
        await message.edit(content="\n".join(lines))
        await message.clear_reaction(emoji)

        await ctx.message.add_reaction(SUCCESS_EMOJI)

    @commands.has_permissions(administrator=True)
    @roles.group(invoke_without_command=True)
    async def category(self, ctx: Context):
        """Command group for managing role categories."""
        await ctx.send_help(self.category)

    @commands.has_permissions(administrator=True)
    @category.command(name="add", aliases=["new", "create"])
    async def category_add(self, ctx: Context, *, title: str):
        """Adds a new category with the given title."""
        title = title.strip("*:")
        await self.channel.send(f"**{title}**:")

        await ctx.message.add_reaction(SUCCESS_EMOJI)

    @commands.has_permissions(administrator=True)
    @category.command(name="delete", aliases=["remove"])
    async def category_delete(self, ctx: Context, category_id: int):
        """Removes a category."""
        await self.bot.db.execute("DELETE FROM roles WHERE category_id = ?", category_id)
        self.role_dict = {
            k: v for k, v in self.role_dict.items()
            if v["category_id"] != category_id
        }

        message = await self.channel.fetch_message(category_id)
        await message.delete()

        await ctx.message.add_reaction(SUCCESS_EMOJI)

    @commands.has_permissions(administrator=True)
    @category.command()
    async def title(self, ctx: Context, category_id: int, *, text: str):
        """Edits a category's title.

           Example usage:
           egg roles category title 797953789826302002 Some cool new title
               - Note that the ** and : are added automatically.
        """
        text = text.strip(":*")
        message = await self.channel.fetch_message(category_id)
        lines = message.content.split("\n")

        if lines[0].startswith("**"):
            lines[0] = f"**{text}:**"
        else:
            lines.insert(0, f"**{text}:**")

        await message.edit(content="\n".join(lines))

        await ctx.message.add_reaction(SUCCESS_EMOJI)

    @Cog.listener(name="on_raw_reaction_add")
    @Cog.listener(name="on_raw_reaction_remove")
    async def handle_reaction(self, payload: RawReactionActionEvent):
        if payload.channel_id != self.channel.id:
            return

        if payload.user_id == self.bot.user.id:
            return

        emoji = payload.emoji
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)

        if str(emoji) not in self.role_dict:
            message = await self.channel.fetch_message(payload.message_id)
            await message.remove_reaction(emoji, member)
            return

        guild = self.bot.get_guild(payload.guild_id)
        role_id = self.role_dict[str(emoji)]["role_id"]
        role = guild.get_role(role_id)

        if payload.event_type == "REACTION_ADD" and role not in member.roles:
            await member.add_roles(role)
        elif payload.event_type == "REACTION_REMOVE" and role in member.roles:
            await member.remove_roles(role)


def setup(bot: utils.Bot):
    bot.add_cog(Roles(bot))
