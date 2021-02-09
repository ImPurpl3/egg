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
from typing import Type

from discord import Guild, VoiceClient
from discord.ext import commands
from discord.ext.commands import (BucketType, Cog, CommandError,
                                  CommandInvokeError, Context)
from youtube_dl.utils import ExtractorError

from voice import MusicPlayer, YTDLSource
from .utils import utils
from .utils.utils import BaseEmbed, format_time

STREAM_MODE = False
URL_REGEX = re.compile(r"https?://(?:www\.)?.+")


class PlayerException(CommandError):
    pass


class Music(Cog):
    def __init__(self, bot: utils.Bot):
        self.bot = bot

    async def cleanup(self, guild: Guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass

        try:
            self.bot.players[guild.id].player_loop.cancel()
            del self.bot.players[guild.id]
        except KeyError:
            pass

    def get_player(self, ctx: Context):
        try:
            player = self.bot.players[ctx.guild.id]
        except KeyError:
            player = MusicPlayer(ctx)
            self.bot.players[ctx.guild.id] = player

        return player

    # async def cog_check(self, ctx: Context) -> bool:
    #     if ctx.author.voice:
    #         return ctx.author.voice.channel.category_id == 788047812729503825
    #     return ctx.channel.category_id == 788047812729503825

    @commands.command(aliases=["join"])
    async def connect(self, ctx: Context):
        embed = BaseEmbed(ctx)
        embed.set_author(
            name=f"Connected to {ctx.author.voice.channel.name}.",
            icon_url=ctx.author.avatar_url
        )
        embed.set_footer(
            text="The music cog is experimental and may not work as intended."
        )

        await ctx.author.voice.channel.connect()
        await ctx.send(embed=embed)


    @commands.command()
    async def pause(self, ctx: Context):
        embed = BaseEmbed(ctx)
        embed.set_author(
            name="Player paused.",
            icon_url=ctx.author.avatar_url
        )

        ctx.voice_client.pause()
        await ctx.send(embed=embed)


    @commands.command(aliases=["stream"])
    @commands.max_concurrency(1, per=BucketType.guild, wait=True)
    async def play(self, ctx: Context, *, query: str):
        vc: VoiceClient = ctx.voice_client
        player: MusicPlayer = self.get_player(ctx)
        player.skipped = None

        do_stream = STREAM_MODE or ctx.invoked_with == "stream"

        async with ctx.typing():
            query = query.strip("<>")

            if not URL_REGEX.match(query):
                query = f"ytsearch:{query}"

            if player.queue.qsize() == 0 \
               and not vc.is_playing() and not vc.is_paused():
                verb = "Playing"

                source = await YTDLSource.from_query(
                    query, loop=self.bot.loop, ctx=ctx, stream=do_stream
                )
                
                player.current = source
                player.first_play_id = ctx.message.id
                await player.queue.put(source)

                data = source.data

            else:
                verb = "Queued"

                if do_stream:
                    source = await YTDLSource.from_query(
                        query, loop=self.bot.loop, partial=True,
                        ctx=ctx, stream=True
                    )
                    data = source
                else:
                    source = await YTDLSource.from_query(
                        query, loop=self.bot.loop, ctx=ctx, stream=False
                    )
                    data = source.data
                
                await player.queue.put(source)

            embed = BaseEmbed(ctx)
            embed.set_author(
                name=f"{verb} {data['title']}",
                icon_url=ctx.author.avatar_url,
                url=data["webpage_url"]
            )

            if data["is_live"]:
                duration = "🔴 LIVE"
            else:
                duration = format_time(data["duration"])

            embed.add_field(name="Uploader", value=data["uploader"])
            embed.add_field(name="Duration", value=duration)
            embed.add_field(name="Requested by", value=ctx.author.mention)

            if verb == "Queued":
                embed.add_field(
                    name="Position in queue", value=player.queue.qsize()
                )

            embed.set_thumbnail(url=data["thumbnail"])

            await ctx.send(embed=embed)


    @commands.command(aliases=["unpause"])
    async def resume(self, ctx: Context):
        embed = BaseEmbed(ctx)
        embed.set_author(
            name="Player resumed.",
            icon_url=ctx.author.avatar_url
        )

        ctx.voice_client.resume()
        await ctx.send(embed=embed)


    @commands.command()
    async def skip(self, ctx: Context):
        player: MusicPlayer = self.get_player(ctx)
        vc: VoiceClient = ctx.voice_client

        if player.queue.qsize() > 0:
            player.current.data["skipper"] = ctx.author
            player.skipped = player.current
        else:
            embed = BaseEmbed(ctx, description="End of queue.")
            embed.set_author(
                name=f"Skipped {player.current.data['title']}",
                icon_url=ctx.author.avatar_url
            )

            await ctx.send(embed=embed)

        vc.stop()


    @commands.command(aliases=["dc", "disconnect"])
    async def stop(self, ctx: Context):
        embed = BaseEmbed(ctx)
        embed.set_author(
            name=f"Disconnected from {ctx.me.voice.channel.name}.",
            icon_url=ctx.author.avatar_url
        )

        await self.cleanup(ctx.guild)
        await ctx.send(embed=embed)


    @commands.command(aliases=["vol"])
    async def volume(self, ctx: Context, value: int):
        vc: VoiceClient = ctx.voice_client
        player: MusicPlayer = self.get_player(ctx)
        old = vc.source.volume

        value = min(max(0, value), 200)  # clamp value to 0-200

        embed = BaseEmbed(ctx)
        embed.set_author(name=f"Volume changed.", icon_url=ctx.author.avatar_url)
        embed.add_field(name="Old volume", value=f"{round(old * 100)}%")
        embed.add_field(name="New volume", value=f"{value}%")

        vc.source.volume = player.volume = value / 100
        await ctx.send(embed=embed)


    @play.error
    async def extraction_error_handler(self, ctx: Context,
                                       error: Type[CommandError]):
        if not isinstance(error, CommandInvokeError):
            return
        
        if isinstance(exc := error.original.__context__, ExtractorError):
            desc = f"{exc.__class__.__name__}: {exc.args[0]}"
            embed = BaseEmbed(ctx, description=f"```css\n{desc}\n```")
            embed.set_author(
                name="An error occurred during data extraction.",
                icon_url=ctx.author.avatar_url
            )

            await ctx.send(embed=embed)

    @connect.before_invoke
    async def can_connect(self, ctx: Context):
        vc: VoiceClient = ctx.voice_client
        if vc is not None:
            embed = BaseEmbed(ctx)
            embed.set_author(
                name="Already connected to a voice channel.",
                icon_url=ctx.author.avatar_url
            )
            await ctx.send(embed=embed)
            raise PlayerException("already connected to a channel")


    @play.before_invoke
    async def ensure_voice(self, ctx: Context):
        vc: VoiceClient = ctx.voice_client

        if not vc or not vc.is_connected:
            if ctx.author.voice:
                await ctx.invoke(self.connect)
            else:
                embed = BaseEmbed(ctx)
                embed.set_author(
                    name="You're not connected to a voice channel.",
                    icon_url=ctx.author.avatar_url
                )
                await ctx.send(embed=embed)
                raise PlayerException("author not connected to voice")


    @pause.before_invoke
    @skip.before_invoke
    @stop.before_invoke
    @resume.before_invoke
    @volume.before_invoke
    async def invalid_operation(self, ctx: Context):
        vc: VoiceClient = ctx.voice_client

        if not vc or not vc.is_connected():
            embed = BaseEmbed(ctx)
            embed.set_author(
                name="Not connected to a voice channel.",
                icon_url=ctx.author.avatar_url
            )
            await ctx.send(embed=embed)

            raise PlayerException("not connected to voice")

        elif not vc.source and ctx.command.name != "stop":
            embed = BaseEmbed(ctx)
            embed.set_author(
                name="Nothing is playing.",
                icon_url=ctx.author.avatar_url
            )
            await ctx.send(embed=embed)

            raise PlayerException("no AudioSource is playing")

        elif vc.is_paused() and ctx.command.name == "pause":
            embed = BaseEmbed(ctx)
            embed.set_author(
                name="Player is already paused.",
                icon_url=ctx.author.avatar_url
            )
            await ctx.send(embed=embed)

            raise PlayerException("player is already paused")

        elif not vc.is_paused() and ctx.command.name == "resume":
            embed = BaseEmbed(ctx)
            embed.set_author(
                name="Player is not paused.",
                icon_url=ctx.author.avatar_url
            )
            await ctx.send(embed=embed)

            raise PlayerException("player is not paused")


def setup(bot: utils.Bot):
    bot.add_cog(Music(bot))
