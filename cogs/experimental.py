from datetime import datetime
from typing import Union

import discord
from discord import (Invite, Member, Message, RawMessageUpdateEvent,
                     RawReactionActionEvent, User, VoiceState, abc)
from discord.ext import commands
from discord.ext.commands import Cog, Context

from cogs.utils import utils

EGG_COLOR = 0xF6DECF


class Experimental(Cog):
    def __init__(self, bot: utils.Bot):
        self.bot = bot

    async def update_last_seen(self, member: Union[Member, User],
                               timestamp: int, *, unsure: bool = False):
        if unsure:
            query = """
                INSERT INTO last_seen (id, time)
                  VALUES (:id, :time)
                    ON CONFLICT (id) DO UPDATE
                      SET time = :time WHERE id = :id
            """

        else:
            query = """
                INSERT INTO last_seen (id, time, guaranteed_time)
                  VALUES (:id, :time, :time)
                    ON CONFLICT (id) DO UPDATE
                      SET time = :time, guaranteed_time = :time WHERE id = :id
            """

        await self.bot.db.execute(query, {"id": member.id, "time": timestamp})

    @Cog.listener()
    async def on_typing(self, channel: abc.Messageable,
                        user: Union[Member, User], when: datetime):
        await self.update_last_seen(user, int(when.timestamp()))

    @Cog.listener()
    async def on_message(self, message: Message):
        await self.update_last_seen(
            message.author, int(message.created_at.timestamp())
        )

    @Cog.listener()
    async def on_raw_message_edit(self, payload: RawMessageUpdateEvent):
        if not payload.cached_message:
            if not payload.data.get("content"):
                return

            if not (user := self.bot.get_user(int(payload.data["author"]["id"]))):
                return
            
            await self.update_last_seen(
                user,
                int(datetime.utcnow().timestamp()),
                unsure=True
            )

        else:
            if payload.data.get("content") != payload.cached_message.content:
                await self.update_last_seen(
                    payload.cached_message.author,
                    int(datetime.utcnow().timestamp())
                )

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        await self.update_last_seen(
            self.bot.get_user(payload.user_id),
            int(datetime.utcnow().timestamp())
        )

    @Cog.listener()
    async def on_member_join(self, member: Member):
        await self.update_last_seen(
            member, int(datetime.utcnow().timestamp())
        )

    @Cog.listener()
    async def on_member_remove(self, member: Member):
        await self.update_last_seen(
            member, int(datetime.utcnow().timestamp())
        )

    @Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        if before.status != after.status or \
           before.activities != after.activities or \
           before.activity != after.activity:
            await self.update_last_seen(
                after, int(datetime.utcnow().timestamp())
            )

    @Cog.listener()
    async def on_user_update(self, before: User, after: User):
        await self.update_last_seen(after, datetime.utcnow().timestamp())

    @Cog.listener()
    async def on_voice_state_update(self, member: Member,
                                    before: VoiceState, after: VoiceState):
        if not before.channel and after.channel:
            await self.update_last_seen(
                member, int(datetime.utcnow().timestamp())
            )
        elif before.self_deaf != after.self_deaf or \
             before.self_mute != after.self_mute or \
             before.self_stream != after.self_stream or \
             before.self_video != after.self_video:
            await self.update_last_seen(
                member, int(datetime.utcnow().timestamp())
            )

    @Cog.listener()
    async def on_invite_create(self, invite: Invite):
        await self.update_last_seen(
            invite.inviter, int(datetime.utcnow().timestamp())
        )

    @commands.command(aliases=["userinfo"])
    async def whois(self, ctx: Context, *, user: utils.GuaranteedUser = None):
        user = user or ctx.author

        if isinstance(user, Member) and user.status != discord.Status.offline:
            await self.update_last_seen(user, int(datetime.utcnow().timestamp()))

        last_seen = await self.bot.db.fetchone(
            "SELECT * FROM last_seen WHERE id = ?", user.id
        )

        if not last_seen:
            ls_value = r"¯\\\_(ツ)\_/¯"

        else:
            unsure = datetime.fromtimestamp(last_seen['time']).strftime(
                "%b %#d %Y, %I:%M:%S %p UTC"
            )
            guaranteed = datetime.fromtimestamp(
                last_seen['guaranteed_time']
            ).strftime("%b %#d %Y, %I:%M:%S %p UTC")

            if last_seen["time"] != last_seen["guaranteed_time"]:
                ls_value = f"{unsure}**?**\n" \
                           f"(last confirmed activity: {guaranteed})"
            else:
                ls_value = guaranteed

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name=str(user), icon_url=ctx.me.avatar_url)

        if user.status != discord.Status.offline:
            embed.add_field(name="Last seen", value=f"{ls_value} (currently online)")
        else:
            embed.add_field(name="Last seen", value=ls_value)

        await ctx.send(embed=embed)

def setup(bot: utils.Bot):
    bot.add_cog(Experimental(bot))
