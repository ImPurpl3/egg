from textwrap import dedent

from discord import Message
from discord.ext import commands
from discord.ext.commands import Cog, Context
from .utils import utils


HELPTEXT = """
    You can give yourself the following roles by using `{0}roles add <ID>` (without <>)
    Removal is similar, the command is `remove` instead of `add`.

    Your roles: {1}

    *Please don't give yourself roles just for the sake of having more roles.*
    *Only take the roles whose channel you really want access to.*
"""


class Roles(Cog):
    def __init__(self, bot: utils.Bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def roles(self, ctx: Context):
        roles = await self.bot.db.fetchall("SELECT * FROM roles")

        author_roles = [f"`{r['short_name']}`" for r in roles \
            if ctx.guild.get_role(r["id"]) in ctx.author.roles]

        author_roles = ", ".join(author_roles) or "None"
        helptext = dedent(HELPTEXT).strip().format(ctx.prefix, author_roles)

        embed = utils.BaseEmbed(ctx, description=helptext)
        embed.set_author(name=f"Opt-in roles", icon_url=ctx.author.avatar_url)

        for role in roles:
            embed.add_field(
                name=role["name"],
                value=f"{role['description']}\n*ID: `{role['short_name']}`*")

        await ctx.send(embed=embed)

    @roles.command()
    async def add(self, ctx: Context, role: str):
        role = await self.bot.db.fetchone("SELECT * FROM roles WHERE short_name = ?", role)

        if not role:
            embed = utils.BaseEmbed(ctx)
            embed.set_author(name="Role not found.", icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed)

        actual_role = ctx.guild.get_role(role["id"])

        if actual_role in ctx.author.roles:
            embed = utils.BaseEmbed(ctx)
            embed.set_author(name="You already have that role.", icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed)

        mention = actual_role.mention

        embed = utils.BaseEmbed(ctx, description=f"Added {mention} to {ctx.author.mention}.")
        embed.set_author(name="Role added.", icon_url=ctx.author.avatar_url)

        await ctx.author.add_roles(actual_role)
        await ctx.send(embed=embed)

    @roles.command()
    async def remove(self, ctx: Context, role: str):
        role = await self.bot.db.fetchone("SELECT * FROM roles WHERE short_name = ?", role)

        if not role:
            embed = utils.BaseEmbed(ctx)
            embed.set_author(name="Role not found.", icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed)

        actual_role = ctx.guild.get_role(role["id"])

        if actual_role not in ctx.author.roles:
            embed = utils.BaseEmbed(ctx)
            embed.set_author(name="You do not have that role.", icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed)

        mention = actual_role.mention

        embed = utils.BaseEmbed(ctx, description=f"Removed {mention} from {ctx.author.mention}.")
        embed.set_author(name="Role removed.", icon_url=ctx.author.avatar_url)

        await ctx.author.remove_roles(actual_role)
        await ctx.send(embed=embed)

    @roles.command()
    @commands.is_owner()
    @commands.has_permissions(administrator=True)
    async def new(self, ctx: Context):
        def is_answer(message: Message):
            return message.author == ctx.author and message.channel == ctx.channel

        async def get_input(is_role=False):
            resp = await self.bot.wait_for("message", check=is_answer)
            await resp.delete()

            if is_role:
                return await commands.RoleConverter().convert(ctx, resp.content)
            return resp.content

        output = ""
        fields = ["Display name", "Short name", "Description", "Role"]
        ans = []

        for field in fields:
            if not output:
                output += f"{field}: "
                msg = await ctx.send(output)

                resp = await get_input()
                output += f"`{resp}`\n"
                ans.append(resp)

                continue

            output += f"{field}: "
            await msg.edit(content=output)

            if field == "Role":
                role = await get_input(is_role=True)
                output += f"`{role.name} ({role.id})`\n"
                ans.append(role.id)
            else:
                resp = await get_input()
                output += f"`{resp}`\n"
                ans.append(resp)

        await self.bot.db.execute(
            "INSERT INTO roles (name, short_name, description, id) VALUES (?, ?, ?, ?)",
            *ans)
        output += f"\nEntry created successfully."

        await msg.edit(content=output)


def setup(bot: utils.Bot):
    bot.add_cog(Roles(bot))
