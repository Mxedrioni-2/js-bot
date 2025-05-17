import discord
from discord.ext import commands
import logging
import os

logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
token = os.getenv('BOT_TOKEN')
@bot.event
async def on_ready():
    logger.info(f'Bot logged in as {bot.user}')
    try:
        await bot.load_extension('cogs.music.music_cog')
        logger.info("Music cog loaded successfully")
    except Exception as e:
        logger.info(f"Error loading Music cog: {e}")

bot.run(token)



    