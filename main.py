import discord
from discord.ext import commands
from redis.asyncio import Redis
from dao.music_dao import MusicDao
from dao.guild_dao import GuildDao
from cogs.music.music_cog import MusicCog
from api.app import create_app
import asyncio
import json
import logging
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = os.getenv("LOG_FORMAT", "text").lower()

    handler = logging.StreamHandler()
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s %(message)s"
        ))

    logging.basicConfig(level=level, handlers=[handler], force=True)
    # discord.py gateway is very noisy at INFO (heartbeats every 40s)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    # uvicorn access log is replaced by our middleware
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)


def create_redis_client() -> Redis:
    url = os.getenv("REDIS_URL")
    if url:
        # Redact credentials from log
        safe = url.split("@")[-1] if "@" in url else url
        logger.info("Connecting to Redis at %s", safe)
        return Redis.from_url(url, decode_responses=True)
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", 6379))
    db = int(os.getenv("REDIS_DB", 0))
    logger.info("Connecting to Redis at %s:%d db=%d", host, port, db)
    return Redis(host=host, port=port, db=db, decode_responses=True)


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    return commands.Bot(command_prefix='!', intents=intents)


async def main():
    token = os.getenv('BOT_TOKEN')
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    redis_client = create_redis_client()
    music_dao = MusicDao(redis_client)
    guild_dao = GuildDao(redis_client)

    bot = create_bot()

    await bot.add_cog(MusicCog(bot, music_dao, guild_dao))
    logger.info("Music cog loaded")

    app = create_app(bot, music_dao, guild_dao)
    log_level = os.getenv("LOG_LEVEL", "INFO").lower()
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level=log_level)
    server = uvicorn.Server(config)

    @bot.event
    async def on_ready():
        guild_names = [g.name for g in bot.guilds]
        logger.info("Bot logged in as %s — connected to %d guild(s): %s",
                    bot.user, len(bot.guilds), guild_names)

    try:
        await asyncio.gather(
            bot.start(token),
            server.serve()
        )
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Shutting down")
        await redis_client.aclose()
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
