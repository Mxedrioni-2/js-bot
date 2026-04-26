import yt_dlp
import discord
import asyncio
import logging
from discord.ext import commands, tasks
from models.song import Song
from dao.music_dao import MusicDao
from dao.guild_dao import GuildDao
from .config import YTDL_CONFIG, FFMPEG_CONFIG, INACTIVITY_TIMEOUT
from .resolver import UrlResolver
from .player import Player
from .playlist import PlaylistLoader

logger = logging.getLogger("music_cog")


class MusicCog(commands.Cog):
    def __init__(self, bot, music_dao: MusicDao, guild_dao: GuildDao, executor):
        self.bot = bot
        self.music_dao = music_dao
        self.guild_dao = guild_dao
        self.executor = executor
        self.last_text_channel = {}
        self.resolver = UrlResolver(bot, YTDL_CONFIG, executor)
        self.player = Player(bot, music_dao, guild_dao, self.resolver, FFMPEG_CONFIG)
        self.playlist_loader = PlaylistLoader(bot, music_dao, self.player, YTDL_CONFIG, executor)
        self.check_inactivity.start()

    def cog_unload(self):
        self.check_inactivity.cancel()

    @tasks.loop(seconds=INACTIVITY_TIMEOUT)
    async def check_inactivity(self):
        for guild in self.bot.guilds:
            guild_id = guild.id
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                continue

            is_inactive = await self.guild_dao.check_inactive(guild_id, INACTIVITY_TIMEOUT)
            is_empty = self.player.vc_is_empty(vc)
            is_playing = vc.is_playing()

            logger.debug("Guild %d: inactive=%s empty=%s playing=%s",
                         guild_id, is_inactive, is_empty, is_playing)

            if (is_inactive and not is_playing) or is_empty:
                logger.info("Guild %d: disconnecting due to inactivity", guild_id)
                await vc.disconnect()
                await self.music_dao.clear_queue(guild_id)
                await self.guild_dao.delete_state(guild_id)
                try:
                    channel = self.last_text_channel.get(guild_id)
                    if channel:
                        await channel.send("კაი გავედი, დამიძახეთ რორამე")
                except discord.Forbidden:
                    continue

    @check_inactivity.error
    async def on_check_inactivity_error(self, error):
        logger.error("check_inactivity task crashed: %s", error, exc_info=error)

    @commands.command()
    async def play(self, ctx, *, url: str):
        if not ctx.author.voice:
            await ctx.send("ვოისში უნდა იყო შესული!")
            return

        guild_id = ctx.guild.id
        logger.info("Guild %d: !play by %s — %s", guild_id, ctx.author, url)
        self.last_text_channel[guild_id] = ctx.channel

        is_playlist = 'list=' in url or '/playlist' in url
        bare_url = url
        if 'list=' in url and 'playlist' not in url:
            bare_url = url.split('&list=')[0].split('?list=')[0]
            is_playlist = False

        status_msg = await ctx.send("ვამუშავებ...")

        resolved, _ = await asyncio.gather(
            self.resolver.resolve_fast(bare_url),
            self.player.ensure_voice(ctx),
        )

        await self.guild_dao.update_last_activity(guild_id)

        if not resolved:
            await status_msg.edit(content="სიმღერის ჩატვირთვა ვერ მოხერხდა")
            return

        vc = ctx.voice_client
        await self.music_dao.queue_song(guild_id, resolved)

        if vc and vc.is_playing():
            await status_msg.edit(content=f"რიგში დაემატა: {resolved.title}")
        else:
            await status_msg.edit(content=f"ვუკრავ: {resolved.title}")
            await self.player.play_next(ctx)

        if is_playlist:
            asyncio.create_task(self.playlist_loader.fetch_background(ctx, url, status_msg))

    @commands.command()
    async def playlist(self, ctx, *, url: str):
        if not ctx.author.voice:
            await ctx.send("ვოისში უნდა იყო შესული!")
            return

        await self.player.ensure_voice(ctx)
        guild_id = ctx.guild.id
        await self.guild_dao.update_last_activity(guild_id)
        self.last_text_channel[guild_id] = ctx.channel

        processing_msg = await ctx.send("ვამუშავებ პლეილისტს...")
        vc = ctx.voice_client
        is_playing = vc and vc.is_playing()

        try:
            config = YTDL_CONFIG.copy()
            config['extract_flat'] = True

            with yt_dlp.YoutubeDL(config) as ydl:
                info = await self.bot.loop.run_in_executor(
                    self.executor, lambda: ydl.extract_info(url, download=False)
                )

            if 'entries' not in info or not info['entries']:
                await processing_msg.edit(content="პლეილისტი ვერ ვიპოვე ან ცარიელია")
                return

            entries = info['entries']
            playlist_title = info.get('title', 'Unknown Playlist')
            await processing_msg.edit(
                content=f"პლეილისტი ნაპოვნია: {playlist_title} - {len(entries)} სიმღერა"
            )

            if not is_playing and entries:
                first = entries[0]
                first_song = Song(
                    url=None,
                    title=first.get('title', 'Unknown Track'),
                    original_url=first.get('webpage_url') or first.get('url'),
                )
                await self.music_dao.queue_song(guild_id, first_song)
                await processing_msg.edit(content=f"ვიწყებ დაკვრას: {first_song.title}")
                await self.player.play_next(ctx)
                asyncio.create_task(
                    self.playlist_loader.load_tracks(ctx, entries[1:], len(entries), processing_msg)
                )
            else:
                asyncio.create_task(
                    self.playlist_loader.load_tracks(ctx, entries, len(entries), processing_msg)
                )

        except Exception as e:
            await processing_msg.edit(content=f"შეცდომა პლეილისტის დამუშავებისას: {str(e)}")

    @commands.command()
    async def loop(self, ctx, mode: str = "show"):
        guild_id = ctx.guild.id
        await self.guild_dao.update_last_activity(guild_id)
        self.last_text_channel[guild_id] = ctx.channel

        loop_modes = ["გამორთული", "ერთი სიმღერა", "რიგი"]

        if mode.lower() == "show":
            current = await self.guild_dao.get_loop_state(guild_id)
            await ctx.send(f"ლუპის რეჟიმი: {loop_modes[current]}")
            return

        if mode.lower() in ["off", "გამორთვა", "0"]:
            await self.guild_dao.set_loop_state(guild_id, 0)
            await ctx.send("ლუპი გამორთულია")
        elif mode.lower() in ["song", "current", "სიმღერა", "1"]:
            await self.guild_dao.set_loop_state(guild_id, 1)
            await ctx.send("ლუპი: მიმდინარე სიმღერა")
        elif mode.lower() in ["queue", "all", "რიგი", "2"]:
            await self.guild_dao.set_loop_state(guild_id, 2)
            await ctx.send("ლუპი: მთლიანი რიგი")
        else:
            await ctx.send("არასწორი რეჟიმი. გამოიყენე: `!loop off`, `!loop song`, ან `!loop queue`")

    @commands.command()
    async def stop(self, ctx):
        if not ctx.voice_client:
            return
        guild_id = ctx.guild.id
        logger.info("Guild %d: !stop by %s", guild_id, ctx.author)
        await self.music_dao.clear_queue(guild_id)
        await self.guild_dao.delete_state(guild_id)
        await ctx.voice_client.disconnect()
        await ctx.send("კაი გავედი, დამიძახეთ რორამე")

    @commands.command()
    async def skip(self, ctx):
        guild_id = ctx.guild.id
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send("არ არის სიმღერა გაშვებული")
            return

        logger.info("Guild %d: !skip by %s", guild_id, ctx.author)
        loop_state = await self.guild_dao.get_loop_state(guild_id)
        if loop_state == 1:
            await self.guild_dao.set_loop_state(guild_id, 0)
            await ctx.send("სიმღერის ლუპი გამორთულია.")

        ctx.voice_client.stop()
        await ctx.send("დავსკიპე")

    @commands.command()
    async def queue(self, ctx):
        guild_id = ctx.guild.id
        songs = await self.music_dao.peek_queue(guild_id)
        loop_state = await self.guild_dao.get_loop_state(guild_id)
        current_song = await self.guild_dao.get_current_song(guild_id)

        loop_modes = ["გამორთული", "სიმღერა", "რიგი"]
        loop_info = f"ლუპის რეჟიმი: {loop_modes[loop_state]}"
        current = f"ახლა უკრავს: {current_song.title}" if current_song else "არ არის სიმღერა გაშვებული"

        if not songs:
            await ctx.send(f"{current}\n{loop_info}\nრიგი ცარიელია")
            return

        queue_text = "\n".join(f"{i}. {s.title}" for i, s in enumerate(songs, 1))
        await ctx.send(f"{current}\n{loop_info}\nრიგი:\n{queue_text}")

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("პაუზა")

    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("გაგრძელება")

    @commands.command()
    async def clear(self, ctx):
        await self.music_dao.clear_queue(ctx.guild.id)
        await ctx.send("რიგის გაწმენდა")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            guild_id = message.guild.id
            await self.guild_dao.update_last_activity(guild_id)
            self.last_text_channel[guild_id] = message.channel
