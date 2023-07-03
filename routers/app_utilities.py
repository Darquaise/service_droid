import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from discord import Intents

from classes import Settings, ServiceDroid

from .auth import AuthContainer
from .exceptions import Unauthorized, RateLimited, InvalidCode

from cogs.startup import StartupCog


class CustomFastAPI(FastAPI):
    bot: ServiceDroid


def create_app(settings: Settings) -> CustomFastAPI:
    def create_bot():
        print("starting bot...")
        intents = Intents.all()

        loop = asyncio.get_event_loop()

        bot = ServiceDroid(
            loop=loop,
            command_prefix="!",
            case_insensitive=True,
            help_command=None,
            debug_guilds=[576380164250927124] if settings.debug else None,
            intents=intents,
            settings=settings
        )

        bot.add_cog(StartupCog(bot))
        loop.create_task(bot.start(token=settings.credentials.token))
        app.bot = bot
        print("bot started")

        # start
        loop.create_task(AuthContainer.start_session(settings))

    app = CustomFastAPI(on_startup=[create_bot])

    return app


def add_to_app(app: CustomFastAPI, server: uvicorn.Server):
    @app.exception_handler(Unauthorized)
    async def unauthorized_error_handler(_, __):
        return JSONResponse(
            {'authenticated': False, 'error': 'Unauthorized'},
            status_code=401
        )

    @app.exception_handler(RateLimited)
    async def rate_limit_error_handler(_, e: RateLimited):
        return JSONResponse(
            {"error": "RateLimited", "retry": e.retry_after, "message": e.message},
            status_code=429,
        )

    @app.exception_handler(InvalidCode)
    async def invalid_code_error_handler(_, __):
        return JSONResponse(
            {"error": "InvalidCode"}
        )

    @app.get('/shutdown')
    async def shutdown_api():
        print("closing bot...")
        await app.bot.close()
        print("bot closed")
        server.should_exit = True
        return "Bot shut down"
