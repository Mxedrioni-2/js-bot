import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv
from api.app import create_app
import asyncio
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(name)s %(message)s'
)
import uvicorn


logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
load_dotenv()
token = os.getenv('BOT_TOKEN')
@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user}')
    try:
        await bot.load_extension('cogs.music.music_cog')
        logger.info("Music cog loaded successfully")
    except Exception as e:
        logger.info(f"Error loading Music cog: {e}")

async def main():
    app = create_app(bot)
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    await asyncio.gather(
        bot.start(token),
        server.serve()
    )

asyncio.run(main())



    