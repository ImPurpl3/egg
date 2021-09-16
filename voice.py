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
import asyncio
import os
from asyncio import AbstractEventLoop
from datetime import datetime
from typing import TypeVar, Union

import discord
from async_timeout import timeout
from cogs.utils import utils
from discord import (AudioSource, FFmpegPCMAudio, Guild, PCMVolumeTransformer,
                     TextChannel)
from discord.ext import commands, tasks
from discord.ext.commands import Cog, Context
from youtube_dl import YoutubeDL

utcnow = datetime.utcnow

Y = TypeVar("Y", bound="YTDLSource")

FFMPEG_EXECUTABLE = "ffmpeg"
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn"
}

ytdl = YoutubeDL({
    "format": "bestaudio/best",
    "outtmpl": "downloads/%(autonumber)s-%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": False,
    "verbose": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "geo_bypass_country": "FI",
    "age_limit": 30
})


class YTDLSource(PCMVolumeTransformer):
    def __init__(self, source: AudioSource, *,
                 data: dict, volume=1.0):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get("title")
        self.url = data.get("url")


    @classmethod
    async def from_query(cls, query: str, *,
                         loop: AbstractEventLoop = None,
                         stream: bool = True, partial: bool = False,
                         ctx: Context = None) -> Union[dict, Y]:
        if not stream and partial:
            raise ValueError("partial cannot be True when not streaming")

        loop = loop or asyncio.get_running_loop()
        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(query, download=not stream)
        )

        if "entries" in data:
            data = data["entries"][0]

        if ctx:
            data["context"] = ctx

        if partial:
            for key in ("formats", "http_headers", "downloader_options", "thumbnails", "url"):
                try:
                    del data[key]
                except Exception:
                    pass
            return data

        options = FFMPEG_OPTIONS.copy()

        if stream:
            source = data["url"]
        else:
            source = ytdl.prepare_filename(data)
            data["filename"] = source
            options.pop("before_options")

        return cls(FFmpegPCMAudio(source, **options), data=data)

    @classmethod
    async def regather_stream(cls, data: dict, *,
                              loop: AbstractEventLoop = None) -> Y:
        loop = loop or asyncio.get_running_loop()
        ctx = data.get("context")
        data = await loop.run_in_executor(
            None,
            lambda: ytdl.extract_info(data["webpage_url"], download=False)
        )

        if ctx:
            data["context"] = ctx

        return cls(FFmpegPCMAudio(data["url"]), data=data)


class MusicPlayer:
    def __init__(self, ctx: Context):
        self.bot: utils.Bot = ctx.bot
        self._channel: TextChannel = ctx.channel
        self._cog: Cog = ctx.cog
        self._guild: Guild = ctx.guild

        self.next = asyncio.Event()
        self.queue = asyncio.Queue()

        self.current = None
        self.volume = 1.0

        self.first_play_id = None
        self.skipped = None

        self.player_loop.start()  # pylint: disable=no-member

    @tasks.loop()
    async def player_loop(self):
        self.next.clear()

        try:
            async with timeout(300):
                source = await self.queue.get()
        except asyncio.TimeoutError:
            print("timeout")
            return await self.destroy(self._guild)

        if not isinstance(source, YTDLSource):
            try:
                source = await YTDLSource.regather_stream(
                    source, loop=self.bot.loop
                )
            except Exception as e:
                embed = discord.Embed(
                    description=f"```css\n{e}\n```",
                    color=0xF6DECF,
                    timestamp=utcnow()
                )
                embed.set_author(
                    name="An error occurred while processing the track.",
                    icon_url=self._guild.me.display_avatar.url
                )

                return await self._channel.send(embed=embed)

        ctx = source.data["context"]

        source.volume = self.volume
        self.current = source

        self._guild.voice_client.play(
            source,
            after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set)
        )

        if self.skipped:
            embed = discord.Embed(
                description=f"**Now playing {self.current.data['title']}**",
                color=0xF6DECF,
                timestamp=utcnow()
            )
            embed.set_author(
                name=f"Skipped {self.skipped.data['title']}",
                icon_url=self.skipped.data["skipper"].display_avatar.url,
                url=source.data["webpage_url"]
            )

            self.skipped = None

            if source.data["is_live"]:
                duration = "🔴 LIVE"
            else:
                duration = utils.format_time(source.data["duration"])

            embed.add_field(name="Uploader", value=source.data["uploader"])
            embed.add_field(name="Duration", value=duration)
            embed.add_field(name="Requested by", value=ctx.author.mention)

            embed.set_thumbnail(url=source.data["thumbnail"])
            await self._channel.send(embed=embed)


        elif ctx.message.id != self.first_play_id:
            embed = discord.Embed(
                color=0xF6DECF, timestamp=utcnow()
            )
            embed.set_author(
                name=f"Now playing {source.title}",
                icon_url=ctx.author.display_avatar.url,
                url=source.data["webpage_url"]
            )

            if source.data["is_live"]:
                duration = "🔴 LIVE"
            else:
                duration = utils.format_time(source.data["duration"])

            embed.add_field(name="Uploader", value=source.data["uploader"])
            embed.add_field(name="Duration", value=duration)
            embed.add_field(name="Requested by", value=ctx.author.mention)

            embed.set_thumbnail(url=source.data["thumbnail"])
            await self._channel.send(embed=embed)

        await self.next.wait()

        source.cleanup()
        self.current = None

        filename = source.data.get("filename")
        if filename and os.path.isfile(filename):
            os.remove(filename)

    @player_loop.before_loop
    async def wait_until_ready(self):
        await self.bot.wait_until_ready()

    def destroy(self, guild: Guild):
        return self._cog.cleanup(guild)
