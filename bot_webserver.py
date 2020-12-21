"""Module containing a web server class used do web server things with the bot."""
import inspect
import logging
import os

import discord
import spotify
from aiohttp import web
from spotify import User

from spotify_credentials import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
from cogs.utils import asqlite, utils

logger = logging.getLogger("aiohttp.web")  # pylint: disable=invalid-name
logger.setLevel(logging.DEBUG)


class WebServer:  # pylint: disable=too-many-instance-attributes
    """Contains various web functions to control the bot through HTTP requests."""
    def __init__(self, bot: utils.Bot):
        self.bot = bot
        self.spotify_client = spotify.Client(CLIENT_ID, CLIENT_SECRET, loop=self.bot.loop)
        self.spotify_user = None

        self.spotify_client_id = CLIENT_ID
        self.spotify_redirect_uri = REDIRECT_URI

        self.app = web.Application(loop=self.bot.loop)

        routes = [web.get("/", self.index)]

        for attr in dir(self):
            obj = getattr(self, attr)
            if inspect.iscoroutinefunction(obj):
                name_split = attr.split("_")
                if len(name_split) < 3:
                    continue
                if name_split[-2] == "callback" and name_split[-1] in ["get", "post"]:
                    method = getattr(web, name_split[-1])
                    routes.append(method(f"/{'_'.join(name_split[:-2])}", obj))

        self.app.add_routes(routes)

        self.bot.loop.create_task(self.run_app())

    async def run_app(self):
        """Runs the internal web server."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", 8888)
        await site.start()

    async def index(self, request: web.Request):
        """If index page is requested, just return their user agent."""
        return web.Response(text=request.headers["User-Agent"])

    async def spotify_callback_get(self, request: web.Request):
        """Used to wait for Spotify authentication."""
        try:
            code = request.query["code"]
        except KeyError:
            try:
                request.query["state"]
            except KeyError:
                return web.Response(text="Nothing to see here.")

            user = self.bot.get_user(self.bot.owner_id)
            self.bot.dispatch("spotify_auth", request.query["error"])
            await user.send(f"Spotify authentication failed.\nReason: `{request.query['error']}`")
            return web.Response(text="Authentication failed.")

        self.spotify_user = await User.from_code(
            self.spotify_client,
            code,
            redirect_uri=REDIRECT_URI)
        self.bot.dispatch("spotify_auth", None)
        return web.Response(text="Authentication successful!")

    async def poopy_callback_post(self, request: web.Request):
        """Used to DM people through a web page."""
        try:
            egg = request.query["egg"]
        except KeyError:
            return web.Response(text="no cumerons for you", status=400)

        if egg != "cum":
            return web.Response(text="bad cummies >:(", status=400)

        user = self.bot.get_user(451124287244468226)
        await user.send(f"poopy {discord.utils.get(self.bot.emojis, name='flushed_ceapa')}")
        return web.Response(text="uwu thanks for cummies")

    async def levels_callback_get(self, request: web.Request):
        """Used to fetch egg bot rank information."""
        if request.headers.get("Authorization") != os.getenv("LEVELS_AUTH"):
            return web.Response(text="403 \N{FLUSHED FACE}", status=403)

        users = []
        level_data = await self.bot.db.fetchall("SELECT * FROM levels ORDER BY xp DESC")

        for position, row in enumerate(level_data):
            user = {
                "name": row["last_known_as"],
                "avatar": row["last_known_avatar_url"],
                "level": row["level"],
                "level_xp": row["level_xp"],
                "levelup_xp": self.bot.cogs["Levels"].get_levelup_xp(row["level"]),
                "total_xp": row["xp"],
                "rank": position + 1
            }
            users.append(user)

        return web.json_response(users)

    async def boost_callback_get(self, request: web.Request):
        """Used to check if a member is boosting the server."""
        if request.headers.get("Authorization") != os.getenv("LEVELS_AUTH"):
            return web.Response(text="403 \N{FLUSHED FACE}", status=403)

        try:
            member_id = request.query["id"]
        except KeyError:
            return web.Response(text="No ID provided \N{FLUSHED FACE}", status=400)

        response = {}
        guild = self.bot.get_guild(527932145273143306)

        try:
            member_id = int(request.query["id"])
        except ValueError:
            response["error"] = "Invalid ID"
            return web.json_response(response)

        if not (member := guild.get_member(member_id)):
            response["error"] = "Invalid ID"
        else:
            response["is_boosting"] = member.premium_since is not None

        return web.json_response(response)

    async def store_callback_get(self, request: web.Request):
        with open("bathwater.html", "r") as f:
            return web.Response(text=f.read(), content_type="text/html")

    async def koth_callback_get(self, request: web.Request):
        async with asqlite.connect("../Howp/data.db") as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM koth_users ORDER BY score DESC")
                data = await cur.fetchall()

                await cur.execute("SELECT * FROM names")
                names = {user["id"]: user["name"] for user in await cur.fetchall()}

        lb = list(list(i) for i in enumerate(data))

        lb[0][0] = "🥇"
        lb[1][0] = "🥈"
        lb[2][0] = "🥉"

        users = []
        for index, user in lb:
            d_index = index if isinstance(index, str) else index + 1
            score = f"{d_index}{'.' if isinstance(index, int) else ''} {names[user['id']]}" \
                    f"{' 👑' if user['has_crown'] else ''}\n" \
                    f"{utils.format_seconds(user['score'])}"
            users.append(score)

        return web.Response(text="\n\n".join(users), charset="utf-8")
