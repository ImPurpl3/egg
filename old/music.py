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
import datetime
import logging
import random
import re

import discord
import humanize
import wavelink
from discord.ext import commands, tasks

# from . import SECRETS as secrets
from .utils import utils

EGG_COLOR = 0xF6DECF
URL_REGEX = re.compile(r"https?:\/\/(?:www\.)?.+")
logging.getLogger("wavelink").setLevel(10)


class Track(wavelink.Track):  # pylint: disable=too-few-public-methods
    """Subclass of wavelink.Track with added features."""
    __slots__ = ("requester", "channel", "message", "f_duration", "loops", "type")

    def __init__(self, id_, info, track_type="standard", *, ctx=None):
        super(Track, self).__init__(id_, info)

        if ctx:
            self.requester = ctx.author
            self.channel = ctx.channel
            self.message = ctx.message

        self.f_duration = Music.format_time(self.duration)
        self.loops = 0
        self.type = track_type

    @property
    def is_dead(self):
        return self.dead


class Player(wavelink.Player):  # pylint: disable=too-many-instance-attributes
    """Subclass of wavelink.Player with added features."""
    def __init__(self, bot: commands.Bot, guild_id: int, node: wavelink.Node):
        super(Player, self).__init__(bot, guild_id, node)

        self.queue = []

        self.volume = 100
        self.inactive = False

        self.loop = False

        self.pauses = set()
        self.resumes = set()
        self.stops = set()
        self.shuffles = set()
        self.skips = set()
        self.repeats = set()

        self.bassboost = False
        self.last_channel = None
        self.last_connected = None
        self.last_track = None


class Music(commands.Cog):  # pylint: disable=too-many-public-methods
    """A cog containing music related commands."""
    def __init__(self, bot: utils.Bot):
        self.bot = bot
        self.hidden = False
        self.playing = False

        if not hasattr(bot, "wavelink"):
            self.bot.wavelink = wavelink.Client(self.bot)

        self.bot.loop.create_task(self.start_nodes())
        self.autodisconnect.start()  # pylint: disable=no-member

        # self.spotify_token = None
        # self.spotify_client_id = secrets.SPOTIFY_CLIENT_ID
        # self.spotify_client_secret = secrets.SPOTIFY_CLIENT_SECRET
        # self.youtube_api_key = secrets.YOUTUBE_API_KEY

    def cog_check(self, ctx: commands.Context):
        return 671872144749101057 in (role.id for role in ctx.author.roles)

    def cog_unload(self):
        self.autodisconnect.cancel()  # pylint: disable=no-member

    @commands.command()
    async def connect(self, ctx):
        """Connects to the voice channel author is in."""

        player = self.get_player(ctx.guild.id)

        if player.is_connected:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(
                name="Already connected to a voice channel.",
                icon_url=ctx.me.avatar.url)
            embed.add_field(name="Channel", value=ctx.me.voice.channel.name)
            return await ctx.send(embed=embed)

        try:
            channel = ctx.author.voice.channel
        except AttributeError:
            embed = discord.Embed(
                description="Join a channel and try again.",
                color=EGG_COLOR,
                timestamp=ctx.message.created_at)
            embed.set_author(
                name="You're not connected to a voice channel.",
                icon_url=ctx.me.avatar.url)
            return await ctx.send(embed=embed)

        player.last_connected = None
        await player.connect(channel.id)
        await asyncio.sleep(1)

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Joined a voice channel.", icon_url=ctx.me.avatar.url)
        embed.add_field(name="Channel", value=ctx.me.voice.channel.name)

        await ctx.send(embed=embed)

    @commands.command(usage="<query>", aliases=["sc", "soundcloud"])
    async def play(self, ctx, *, query: str = None):  # pylint: disable=too-many-branches, too-many-statements,
        """Plays a song.
        ``query`` can be a link or a YouTube search.
        ``play`` supports sites like YouTube, SoundCloud etc.
        The ``sc``/``soundcloud`` alias forces a SoundCloud search. Useful for playing Spotify playlists via SC.
        """  # pylint: disable=line-too-long
        player = self.get_player(ctx.guild.id)

        if player.paused and not query:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Player resumed.", icon_url=ctx.me.avatar.url)

            await player.set_pause(False)
            await ctx.send(embed=embed)

        elif not player.paused and not query:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Player is not paused.", icon_url=ctx.me.avatar.url)

            return await ctx.send(embed=embed)

        query = query.strip("<>")

        start_queue = not player.queue and not player.is_playing

        if not player.is_connected:
            await ctx.invoke(self.connect)
            try:
                if ctx.author.voice.channel is None:
                    return
            except AttributeError:
                return

        if not player.queue:
            player.last_channel = ctx.channel

        if "https://open.spotify.com/" in query:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(
                name="Spotify functionality is not implemented yet.",
                icon_url=ctx.me.avatar.url)
            await ctx.send()
            # await self.spotify_queue(ctx, player, query, start_queue)

        else:
            if not URL_REGEX.match(query):
                if ctx.invoked_with in ["sc", "soundcloud"]:
                    query = f"scsearch:{query}"
                else:
                    query = f"ytsearch:{query}"

            else:
                if ctx.invoked_with in ["sc", "soundcloud"]:
                    soundcloud_links = ("https://soundcloud.com/", "https://www.soundcloud.com/")
                    if not query.startswith(soundcloud_links):
                        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                        embed.set_author(name="Invalid SoundCloud URL.", icon_url=ctx.me.avatar.url)
                        return await ctx.send(embed=embed)

            tracks = await self.bot.wavelink.get_tracks(query)
            if not tracks:
                embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                embed.set_author(name="No songs found.", icon_url=ctx.me.avatar.url)
                return await ctx.send(embed=embed)

            if isinstance(tracks, wavelink.TrackPlaylist):
                for track in tracks.tracks:
                    player.queue.append(Track(track.id, track.info, ctx=ctx))

                embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                embed.set_author(name="Playlist queued.", icon_url=ctx.me.avatar.url)
                embed.add_field(
                    name="Playlist",
                    value=tracks.data["playlistInfo"]["name"],
                    inline=False)
                embed.add_field(
                    name="Duration",
                    value=f"{self.format_time(sum([track.duration for track in tracks.tracks]))}" \
                          f"({len(tracks.tracks)} songs)",
                    inline=False)
                if URL_REGEX.match(query):
                    embed.add_field(name="URL", value=query, inline=False)

                if tracks.tracks[0].thumb:
                    embed.set_thumbnail(
                        url=tracks.tracks[0].thumb.replace("default", "maxresdefault"))

                await ctx.send(embed=embed)

            else:
                raw_track = tracks[0]
                track = Track(raw_track.id, raw_track.info, ctx=ctx)

                if player.queue and not start_queue:
                    embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                    embed.set_author(name="Song queued.", icon_url=ctx.me.avatar.url)
                    embed.add_field(name="Song", value=track.title, inline=False)
                    embed.add_field(name="Duration", value=track.f_duration, inline=False)
                    embed.add_field(name="URL", value=track.uri, inline=False)

                    if track.thumb:
                        embed.set_thumbnail(url=track.thumb.replace("default", "maxresdefault"))

                    await ctx.send(embed=embed)

                player.queue.append(track)

            if start_queue:
                player.last_channel = ctx.channel

                embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                embed.set_author(name="Now playing:", icon_url=ctx.me.avatar.url)
                embed.add_field(name="Song", value=player.queue[0].title)
                embed.add_field(name="Duration", value=player.queue[0].f_duration)
                embed.add_field(name="Requested by", value=player.queue[0].requester.mention)
                embed.add_field(name="URL", value=player.queue[0].uri)

                if player.queue[0].thumb:
                    embed.set_thumbnail(
                        url=player.queue[0].thumb.replace("default", "maxresdefault"))

                await ctx.send(embed=embed)
                track = player.queue.pop(0)
                await player.play(track)
                player.last_track = track

    @commands.command()
    async def pause(self, ctx):
        """Pauses the player."""
        player = self.get_player(ctx.guild.id)

        if not player.is_connected:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Not connected to a voice channel.", icon_url=ctx.me.avatar.url)

            await ctx.send(embed=embed)

        elif player.is_connected and not player.is_playing and not player.queue:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Player is not playing.", icon_url=ctx.me.avatar.url)

            await ctx.send(embed=embed)

        elif player.paused:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Player is already paused.", icon_url=ctx.me.avatar.url)

            await ctx.send(embed=embed)

        else:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Player paused.", icon_url=ctx.me.avatar.url)

            await player.set_pause(True)
            await ctx.send(embed=embed)

    @commands.command(aliases=["unpause"])
    async def resume(self, ctx):
        """Resumes the player."""
        player = self.get_player(ctx.guild.id)

        if player.paused:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Player resumed.", icon_url=ctx.me.avatar.url)

            await player.set_pause(False)
            await ctx.send(embed=embed)

        else:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Player is not paused.", icon_url=ctx.me.avatar.url)

            await ctx.send(embed=embed)

    @commands.command(aliases=["q"], usage="(page)")
    async def queue(self, ctx, page_number: int = None):
        """
        Displays the player queue.
        ``page_number`` defaults to the first page.
        """

        player = self.get_player(ctx.guild.id)

        if not player.queue:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Queue is empty.", icon_url=ctx.me.avatar.url)
            return await ctx.send(embed=embed)

        pages = self.slicer(list(player.queue), 10)

        if not page_number:
            page_number = 1
        elif page_number > len(pages):
            page = len(pages)
        else:
            page = page_number

        page = pages[page_number - 1]

        description = ""

        if not any(isinstance(track, str) for track in player.queue):
            total_duration = self.format_time(
                sum([track.duration for track in player.queue]) \
                + (player.current.duration - player.position))
            description += f"**Total duration: {total_duration}**"

        for track, i in zip(page, range(len(page))):
            if isinstance(track, wavelink.Track):
                title = track.title
            else:
                title = track[5:]

            description += f"\n\n**{i + 1}.** ``{title}``"

        embed = discord.Embed(
            title=f"Now playing: {player.current.title} " \
                  f"({self.format_time(player.position)} / " \
                  f"{self.format_time(player.current.duration)})",
            description=description,
            color=EGG_COLOR,
            timestamp=ctx.message.created_at
        )

        embed.set_author(
            name=f"Player queue ({len(player.queue)} songs)",
            icon_url=ctx.me.avatar.url)
        embed.set_footer(text=f"Page {page_number}/{len(pages)}")

        await ctx.send(embed=embed)

    @commands.command()
    async def clear(self, ctx):
        """Clears the queue."""
        player = self.get_player(ctx.guild.id)

        if not player.queue:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="There's nothing to clear.")
            return await ctx.send(embed=embed)

        player.queue = []

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Queue cleared.", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed)

    @commands.command()
    async def remove(self, ctx, index: int):
        """Removes a song from the queue."""
        player = self.get_player(ctx.guild.id)

        if not player.queue:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Queue is empty.", icon_url=ctx.me.avatar.url)
            return await ctx.send(embed=embed)

        track = player.queue.pop(index - 1)

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Track removed.", icon_url=ctx.me.avatar.url)
        embed.add_field(
            name="Track",
            value=track.title if isinstance(track, wavelink.Track) else track)
        await ctx.send(embed=embed)

    @commands.command()
    async def loop(self, ctx):
        """Toggles player looping."""

        player = self.get_player(ctx.guild.id)

        if player.is_connected:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(
                name="Looping disabled." if player.loop is True else "Looping enabled.",
                icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed)
            player.loop = not player.loop

        else:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Not connected to a voice channel.", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed)

    @commands.command()
    async def shuffle(self, ctx):
        """Shuffles the queue."""

        player = self.get_player(ctx.guild.id)

        if player.is_connected:
            if not player.queue:
                embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
                embed.set_author(name="Queue is empty.", icon_url=ctx.me.avatar.url)
                return await ctx.send(embed=embed)

            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Queue shuffled.", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed)

            random.shuffle(player.queue)

            if not isinstance(player.queue[0], wavelink.Track):
                if player.queue[0].startswith("[SC]"):
                    search_type = "scsearch:"
                else:
                    search_type = "ytsearch:"
                await ctx.send(f"{search_type}{player.queue[0][5:]}")
                tracks = await self.bot.wavelink.get_tracks(f"{search_type}{player.queue[0][5:]}")
                track = tracks[0]
                player.queue[0] = Track(track.id, track.info, "spotify")

        else:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Not connected to a voice channel.", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed)

    @commands.command()
    async def bassboost(self, ctx):
        """Toggles bass boost on or off."""

        player = self.get_player(ctx.guild.id)

        if not player.is_connected:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Not connected to a voice channel.", icon_url=ctx.me.avatar.url)
            return await ctx.send(embed=embed)

        if player.bassboost is False:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Bass boost enabled.", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed)

            await player.set_preq("BOOST")
            player.bassboost = True

        else:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Bass boost disabled.", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed)

            await player.set_preq("FLAT")
            player.bassboost = False

    @commands.command(usage="(volume)")
    async def volume(self, ctx, volume: int = None):
        """
        Changes the player volume to ``volume``.
        If ``volume`` is not given, shows the current volume.
        """

        player = self.get_player(ctx.guild.id)

        if not player.is_connected:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Not connected to a voice channel.", icon_url=ctx.me.avatar.url)
            return await ctx.send(embed=embed)

        if not volume:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name=f"Current volume: {player.volume}%", icon_url=ctx.me.avatar.url)
            return await ctx.send(embed=embed)

        if volume < 0 or volume > 1000:
            embed = discord.Embed(
                description="Enter a valid volume (between 0 and 1000).",
                color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Invalid volume.", icon_url=ctx.me.avatar.url)
            return await ctx.send(embed=embed)

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Volume changed.", icon_url=ctx.me.avatar.url)
        embed.add_field(name="New volume", value=str(volume) + "%")
        embed.add_field(name="Old volume", value=str(player.volume) + "%")

        await ctx.send(embed=embed)
        await player.set_volume(volume)

    @commands.command(aliases=["stop", "dc"])
    async def disconnect(self, ctx):
        """Disconnects from current voice channel"""

        player = self.get_player(ctx.guild.id)

        if player.is_connected:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Disconnected.", icon_url=ctx.me.avatar.url)
            embed.add_field(name="Channel", value=ctx.me.voice.channel.name)

            await ctx.send(embed=embed)

            await player.disconnect()
            player.queue = []
            await player.stop()
            player.loop = False

            player.last_connected = datetime.datetime.utcnow()

        else:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Not connected to a voice channel.", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed)

    @commands.command()
    async def skip(self, ctx):
        """Skips the current song."""

        player = self.get_player(ctx.guild.id)

        if player.is_connected and player.is_playing is True:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Song skipped.", icon_url=ctx.me.avatar.url)
            embed.add_field(name="Song", value=player.current.title, inline=False)
            embed.add_field(
                name="Now playing",
                value=player.queue[0].title if player.queue else "None",
                inline=False)

            await ctx.send(embed=embed)

            if player.loop is True:
                player.loop = False
                await player.stop()
                player.loop = True

            else:
                await player.stop()

        elif player.is_connected and not player.is_playing and not player.queue:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="There's nothing to skip.", icon_url=ctx.me.avatar.url)

            await ctx.send(embed=embed)

        elif not player.is_connected:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Not connected to a voice channel.", icon_url=ctx.me.avatar.url)

            await ctx.send(embed=embed)

        else:
            await ctx.send(
                f"player.is_connected: {player.is_connected}\n" \
                f"player.is_playing: {player.is_playing}\n" \
                f"player.queue: {player.queue}")

    @commands.command()
    async def wavelinkinfo(self, ctx):
        """Retrieve various Node/Server/Player information."""

        player = self.get_player(ctx.guild.id)
        node = player.node

        used = humanize.naturalsize(node.stats.memory_used)
        total = humanize.naturalsize(node.stats.memory_allocated)
        free = humanize.naturalsize(node.stats.memory_free)
        cpu = node.stats.cpu_cores

        embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
        embed.set_author(name="Wavelink information", icon_url=ctx.me.avatar.url)
        embed.add_field(name="Connected nodes", value=len(self.bot.wavelink.nodes))
        embed.add_field(
            name="Best available node",
            value=self.bot.wavelink.get_best_node().__repr__())
        embed.add_field(name="Total players", value=node.stats.players)
        embed.add_field(name="Lavalink server memory", value=f"{used}/{total} ({free} free)")
        embed.add_field(name="Lavalink CPU cores", value=cpu)
        embed.add_field(
            name="Lavalink uptime",
            value=datetime.timedelta(milliseconds=node.stats.uptime))

        await ctx.send(embed=embed)

    @commands.command()
    async def resetplayer(self, ctx):
        """If the player freezes or breaks in any other way, run this command."""

        player = self.get_player(ctx.guild.id)

        if not player.is_connected:
            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Not connected to a voice channel.", icon_url=ctx.me.avatar.url)

            await ctx.send(embed=embed)

        else:
            embed = discord.Embed(
                description="This will wipe the current queue.",
                color=EGG_COLOR,
                timestamp=ctx.message.created_at)
            embed.set_author(
                name="Are you sure you want to reset the player?",
                icon_url=ctx.me.avatar.url)
            message = await ctx.send(embed=embed)

            guild = self.bot.get_guild(476812249693028354)
            emojis = [
                discord.utils.get(guild.emojis, name=f"yes"),
                discord.utils.get(guild.emojis, name=f"no")]

            for emoji in emojis:
                await message.add_reaction(emoji)

            def check(reaction: discord.Reaction, user: discord.Member):
                return user == ctx.author \
                       and reaction.message.id == message.id \
                       and reaction.emoji in emojis

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", check=check, timeout=10)
            except asyncio.TimeoutError:
                message2 = await ctx.send("Canceling.")
                await message2.delete()
                await message.delete()
                await ctx.message.delete()
                return

            if "no" in reaction.emoji.name:
                message2 = await ctx.send("Canceling.")
                await asyncio.sleep(1)
                await message2.delete()
                await message.delete()
                await ctx.message.delete()
                return

            await message.delete()

            channel = ctx.me.voice.channel

            embed = discord.Embed(color=EGG_COLOR, timestamp=ctx.message.created_at)
            embed.set_author(name="Player reset.", icon_url=ctx.me.avatar.url)

            await player.disconnect()
            await asyncio.sleep(1)
            await player.destroy()
            await asyncio.sleep(1)

            player = self.get_player(ctx.guild.id)

            await player.connect(channel.id)
            await ctx.send(embed=embed)

    # Wavelink methods

    async def start_nodes(self):
        """Starts Wavelink nodes."""
        await self.bot.wait_until_ready()

        node = self.bot.wavelink.get_node("HOOP")

        if not node:
            node = await self.bot.wavelink.initiate_node(host="0.0.0.0",
                                                         port=2333,
                                                         rest_uri="http://0.0.0.0:2333",
                                                         password="test",
                                                         identifier="EGG",
                                                         region="eu_west")
        node.set_hook(self.event_hook)

    async def event_hook(self, event):  # pylint: disable=too-many-branches, too-many-statements
        """Fired on every Lavalink event."""
        if isinstance(event, wavelink.TrackEnd):
            # print(event)
            player = event.player

            if player.loop:
                player.last_track.loops += 1

                embed = discord.Embed(
                    color=EGG_COLOR,
                    timestamp=datetime.datetime.utcnow())
                embed.set_author(
                    name=f"Looping {player.last_track.title}.",
                    icon_url=self.bot.user.avatar.url)
                embed.add_field(name="Loops", value=player.last_track.loops)

                await player.last_channel.send(embed=embed)
                await player.play(player.last_track)

            elif len(player.queue) > 0:
                try:
                    player.last_channel = player.queue[0].channel
                except AttributeError:
                    pass

                embed = discord.Embed(
                    color=EGG_COLOR,
                    timestamp=datetime.datetime.utcnow())
                embed.set_author(name="Now playing:", icon_url=self.bot.user.avatar.url)
                embed.add_field(name="Song", value=player.queue[0].title)
                embed.add_field(name="Duration", value=player.queue[0].f_duration)
                if player.queue[0].type == "standard":
                    embed.add_field(name="Requested by", value=player.queue[0].requester.mention)
                embed.add_field(name="URL", value=player.queue[0].uri)

                if player.queue[0].thumb:
                    embed.set_thumbnail(
                        url=player.queue[0].thumb.replace("default", "maxresdefault"))

                try:
                    await player.queue[0].channel.send(embed=embed)
                except AttributeError:
                    await player.last_channel.send(embed=embed)
                next_song = player.queue.pop(0)
                await player.play(next_song)
                player.last_track = next_song

                if not player.queue:
                    return

                if not isinstance(player.queue[0], wavelink.Track):
                    for track in player.queue[:]:
                        if "[sc]" in track.lower():
                            search_type = "scsearch:"
                        else:
                            search_type = "ytsearch:"

                        tracks = await self.bot.wavelink.get_tracks(f"{search_type}{track[5:]}")

                        if not tracks and search_type == "scsearch:":
                            tracks = await self.bot.wavelink.get_tracks(f"ytsearch:{track[5:]}")

                        if not tracks:
                            player.queue.remove(track)
                            continue
                        break

                    track = tracks[0]

                    player.queue[0] = Track(track.id, track.info, "spotify")

            else:
                if event.player.is_connected:
                    embed = discord.Embed(
                        color=EGG_COLOR,
                        timestamp=datetime.datetime.utcnow())
                    embed.set_author(name="Queue ended.", icon_url=self.bot.user.avatar.url)

                    await player.stop()
                    await player.last_channel.send(embed=embed)

        elif isinstance(event, wavelink.TrackException):
            print(event.error)

        elif isinstance(event, wavelink.TrackStuck):
            await event.player.last_channel.send(
                f"Track stuck.\n\n``{event.track}``\n``{event.threshold}``")

    # Background tasks

    @tasks.loop(minutes=5)
    async def autodisconnect(self):
        """Disconnects bot from every channel that it's not used in."""
        for _, player in self.bot.wavelink.players.items():
            if player.is_connected and not player.is_playing and not player.queue:
                channel = player.last_channel
                await player.disconnect()
                player.last_connected = datetime.datetime.utcnow()

                embed = discord.Embed(
                    color=EGG_COLOR,
                    timestamp=datetime.datetime.utcnow())
                embed.set_author(
                    name="Disconnecting for inactivity.",
                    icon_url=channel.guild.me.avatar.url)
                await channel.send(embed=embed)

    # Helper methods

    @classmethod
    def format_time(cls, time: int) -> str:
        """Formats milliseconds to a HH:MM:SS string."""
        hours, remainder = divmod(time / 1000, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}"

    @staticmethod
    def slicer(list_: list, amount: int) -> list:
        """Slices a list into amount equal parts."""
        sliced_list = []

        for i in range(0, len(list_), amount):
            sliced_list.append(list_[i:i + amount])

        return sliced_list

    def get_player(self, guild_id: int) -> Player:
        """Gets a Player instance."""
        player = self.bot.wavelink.get_player(guild_id, cls=Player)

        return player

    # Spotify-related helpers


def setup(bot: utils.Bot) -> None:
    """Entry point for bot.load_extension."""
    bot.add_cog(Music(bot))
