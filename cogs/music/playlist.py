import yt_dlp
import logging
from models.song import Song

logger = logging.getLogger("music_cog.playlist")


class PlaylistLoader:
    def __init__(self, bot, music_dao, player, ytdl_config: dict, executor):
        self.bot = bot
        self.music_dao = music_dao
        self.player = player
        self.ytdl_config = ytdl_config
        self.executor = executor

    async def fetch_background(self, ctx, url: str, status_msg):
        config = self.ytdl_config.copy()
        config['extract_flat'] = True
        guild_id = ctx.guild.id
        try:
            with yt_dlp.YoutubeDL(config) as ydl:
                info = await self.bot.loop.run_in_executor(
                    self.executor, lambda: ydl.extract_info(url, download=False)
                )
            if 'entries' not in info:
                return
            for entry in info['entries']:
                if entry:
                    await self.music_dao.queue_song(guild_id, Song(
                        url=None,
                        title=entry.get('title', 'Unknown Track'),
                        original_url=entry.get('webpage_url') or entry.get('url'),
                    ))
            await status_msg.edit(
                content=f"პლეილისტი ჩაიტვირთა: {info.get('title', '?')} — {len(info['entries'])} სიმღერა"
            )
        except Exception as e:
            await status_msg.edit(content=f"პლეილისტის ჩატვირთვა ვერ მოხერხდა: {e}")

    async def load_tracks(self, ctx, entries, total_songs: int, status_msg):
        guild_id = ctx.guild.id
        songs_added = 0

        for i, entry in enumerate(entries):
            if not entry:
                continue
            await self.music_dao.queue_song(guild_id, Song(
                url=None,
                title=entry.get('title', 'Unknown Track'),
                original_url=entry.get('webpage_url') or entry.get('url'),
            ))
            songs_added += 1
            if i % 10 == 0:
                await status_msg.edit(content=f"დამატებულია {songs_added}/{total_songs} სიმღერა...")

        await status_msg.edit(content=f"რიგში დაემატა {songs_added} სიმღერა პლეილისტიდან")

        if not ctx.voice_client.is_playing():
            await self.player.play_next(ctx)
