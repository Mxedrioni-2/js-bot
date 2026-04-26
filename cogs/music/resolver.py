import yt_dlp
import logging
from models.song import Song

logger = logging.getLogger("music_cog.resolver")


class UrlResolver:
    def __init__(self, bot, ytdl_config: dict, executor):
        self.bot = bot
        self.ytdl_config = ytdl_config
        self.executor = executor

    async def resolve(self, original_url: str) -> Song | None:
        logger.debug("Resolving URL: %s", original_url)
        try:
            with yt_dlp.YoutubeDL(self.ytdl_config) as ydl:
                info = await self.bot.loop.run_in_executor(
                    self.executor, lambda: ydl.extract_info(original_url, download=False)
                )
                if 'entries' in info:
                    info = info['entries'][0]
                song = Song(
                    url=info.get('url'),
                    title=info.get('title', 'Unknown Track'),
                    original_url=original_url,
                )
                logger.debug("Resolved '%s'", song.title)
                return song
        except Exception as e:
            logger.error("Failed to resolve URL %s: %s", original_url, e)
            return None

    async def resolve_fast(self, url: str) -> Song | None:
        logger.debug("Fast-resolving URL: %s", url)
        config = self.ytdl_config.copy()
        config['noplaylist'] = True
        config['extract_flat'] = False
        try:
            with yt_dlp.YoutubeDL(config) as ydl:
                info = await self.bot.loop.run_in_executor(
                    self.executor, lambda: ydl.extract_info(url, download=False)
                )
                if 'entries' in info:
                    info = info['entries'][0]
                song = Song(
                    url=info.get('url'),
                    title=info.get('title', 'Unknown Track'),
                    original_url=url,
                )
                logger.debug("Fast-resolved '%s'", song.title)
                return song
        except Exception as e:
            logger.error("Fast resolve failed for %s: %s", url, e)
            return None
