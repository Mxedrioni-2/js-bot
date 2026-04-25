import discord
from discord.ext import commands
from redis.asyncio import Redis
from dao.music_dao import MusicDao
from dao.guild_dao import GuildDao
from cogs.music.music_cog import MusicCog
from api.app import create_app
import asyncio
import logging
import uvicorn
import os
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

def create_redis_client() -> Redis:
    url = os.getenv("REDIS_URL")
    if url:
        return Redis.from_url(url, decode_responses=True)
    return Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        decode_responses=True
    )

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
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    @bot.event
    async def on_ready():
        logger.info(f"Bot logged in as {bot.user}")

    try:
        await asyncio.gather(
            bot.start(token),
            server.serve()
        )
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Shutting down...")
        await redis_client.aclose()
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())