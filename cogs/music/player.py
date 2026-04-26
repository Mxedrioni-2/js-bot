import discord
import asyncio
import logging
from .resolver import UrlResolver

logger = logging.getLogger("music_cog.player")


class Player:
    def __init__(self, bot, music_dao, guild_dao, resolver: UrlResolver, ffmpeg_config: dict):
        self.bot = bot
        self.music_dao = music_dao
        self.guild_dao = guild_dao
        self.resolver = resolver
        self.ffmpeg_config = ffmpeg_config

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        loop_state = await self.guild_dao.get_loop_state(guild_id)
        current_song = await self.guild_dao.get_current_song(guild_id)

        if loop_state == 1 and current_song:
            next_song = await self.resolver.resolve(current_song.original_url)
            if not next_song:
                await ctx.send("სიმღერის ხელახლა ჩატვირთვა ვერ მოხერხდა")
                return
        else:
            next_song = await self.music_dao.pop_song(guild_id)
            if not next_song:
                return

            if loop_state == 2 and current_song:
                await self.music_dao.queue_song(guild_id, current_song)

            if next_song.url is None:
                next_song = await self.resolver.resolve(next_song.original_url)
                if not next_song:
                    await ctx.send("სიმღერა ვერ ჩაიტვირთა, ვაგრძელებ...")
                    await self.play_next(ctx)
                    return

        await self.guild_dao.set_current_song(guild_id, next_song)
        logger.info("Guild %d: now playing '%s'", guild_id, next_song.title)

        try:
            source = discord.FFmpegOpusAudio(next_song.url, **self.ffmpeg_config)

            def after_playing(error):
                if error:
                    logger.error("Guild %d: playback error: %s", guild_id, error)
                asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)

            ctx.voice_client.play(source, after=after_playing)

            loop_msg = " (ლუპში)" if loop_state == 1 else ""
            await ctx.send(f'ახლა ვუკრავ: {next_song.title}{loop_msg}')

        except Exception as e:
            logger.error("Guild %d: failed to start playback: %s", guild_id, e)
            await ctx.send(f"დამენძრა: {str(e)}")
            await self.play_next(ctx)

    async def ensure_voice(self, ctx):
        if ctx.voice_client:
            if not ctx.voice_client.is_connected():
                await ctx.voice_client.disconnect(force=True)
                await asyncio.sleep(1)
                await ctx.author.voice.channel.connect()
        else:
            await ctx.author.voice.channel.connect()

    def vc_is_empty(self, vc) -> bool:
        if not vc or not vc.channel:
            return True
        return len([m for m in vc.channel.members if not m.bot]) == 0
