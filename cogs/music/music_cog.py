from discord.ext import commands, tasks
import yt_dlp
import discord
import asyncio
import time
from models.song import Song
from dao.music_dao import MusicDao
from dao.guild_dao import GuildDao
import logging

logger = logging.getLogger("music_cog")

class MusicCog(commands.Cog):
    def __init__(self, bot, music_dao: MusicDao, guild_dao: GuildDao):
        self.bot = bot
        self.music_dao = music_dao
        self.guild_dao = guild_dao
        self.inactivity_timeout = 180
        self.last_text_channel = {}  # stays in-memory, it's a discord object, can't serialize
        self.ytdl_config = {
            'format': 'bestaudio/best',
            'noplaylist': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'skip_download': True,
            'buffersize': 4096,
            'concurrent_fragment_downloads': 5,
            'socket_timeout': 10,
            'retries': 3,
        }
        self.ffmpeg_config = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -ar 48000 -ac 2 -b:a 128k -bufsize 4096k',
        }
        self.check_inactivity.start()

    def cog_unload(self):
        self.check_inactivity.cancel()

    @tasks.loop(seconds=180)
    async def check_inactivity(self):
        for guild in self.bot.guilds:
            guild_id = guild.id
            vc = guild.voice_client
            if not vc or not vc.is_connected():
                continue

            is_inactive = await self.guild_dao.check_inactive(guild_id, self.inactivity_timeout)
            is_empty = self.vc_is_empty(vc)
            is_playing = vc.is_playing()

            logger.info(f"Guild {guild_id}: inactive={is_inactive}, empty={is_empty}, playing={is_playing}")

            if (is_inactive and not is_playing) or is_empty:
                logger.info(f"Guild {guild_id}: disconnecting due to inactivity")
                await vc.disconnect()
                await self.music_dao.clear_queue(guild_id)
                await self.guild_dao.delete_state(guild_id)
                try:
                    channel = self.last_text_channel.get(guild_id)
                    if channel:
                        await channel.send("კაი გავედი, დამიძახეთ რორამე")
                except discord.Forbidden:
                    continue

    @check_inactivity.before_loop
    async def before_check_inactivity(self):
        await self.bot.wait_until_ready()

    async def resolve_url(self, original_url: str) -> Song | None:
        try:
            with yt_dlp.YoutubeDL(self.ytdl_config) as ydl:
                info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(original_url, download=False))
                if 'entries' in info:
                    info = info['entries'][0]
                return Song(
                    url=info.get('url'),
                    title=info.get('title', 'Unknown Track'),
                    original_url=original_url
                )
        except Exception as e:
            logger.error(f"Error resolving URL: {e}")
            return None

    async def resolve_url_fast(self, url: str) -> Song | None:
        config = self.ytdl_config.copy()
        config['noplaylist'] = True
        config['extract_flat'] = False
        try:
            with yt_dlp.YoutubeDL(config) as ydl:
                info = await self.bot.loop.run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
                if 'entries' in info:
                    info = info['entries'][0]
                return Song(
                    url=info.get('url'),
                    title=info.get('title', 'Unknown Track'),
                    original_url=url
                )
        except Exception as e:
            print(f"Fast resolve error: {e}")
            return None

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        loop_state = await self.guild_dao.get_loop_state(guild_id)
        current_song = await self.guild_dao.get_current_song(guild_id)

        if loop_state == 1 and current_song:
            next_song = await self.resolve_url(current_song.original_url)
            if not next_song:
                await ctx.send("სიმღერის ხელახლა ჩატვირთვა ვერ მოხერხდა")
                return
        else:
            next_song = await self.music_dao.pop_song(guild_id)
            if not next_song:
                return

            if loop_state == 2 and current_song:
                await self.music_dao.queue_song(guild_id, current_song)

            next_song = await self.resolve_url(next_song.original_url)
            if not next_song:
                await ctx.send("სიმღერა ვერ ჩაიტვირთა, ვაგრძელებ...")
                await self.play_next(ctx)
                return

        await self.guild_dao.set_current_song(guild_id, next_song)

        try:
            source = await discord.FFmpegOpusAudio.from_probe(
                next_song.url,
                **self.ffmpeg_config,
                method='fallback'
            )

            def after_playing(error):
                if error:
                    logger.error(f"დამენძრა: {error}")
                asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)

            ctx.voice_client.play(source, after=after_playing)

            loop_msg = " (ლუპში)" if loop_state == 1 else ""
            await ctx.send(f'ახლა ვუკრავ: {next_song.title}{loop_msg}')

        except Exception as e:
            await ctx.send(f"დამენძრა: {str(e)}")
            await self.play_next(ctx)

    async def fetch_playlist_background(self, ctx, url: str, status_msg):
        config = self.ytdl_config.copy()
        config['extract_flat'] = True
        guild_id = ctx.guild.id
        try:
            with yt_dlp.YoutubeDL(config) as ydl:
                info = await self.bot.loop.run_in_executor(
                    None, lambda: ydl.extract_info(url, download=False)
                )
            if 'entries' not in info:
                return
            for entry in info['entries']:
                if entry:
                    await self.music_dao.queue_song(guild_id, Song(
                        url=None,
                        title=entry.get('title', 'Unknown Track'),
                        original_url=entry.get('webpage_url') or entry.get('url')
                    ))
            await status_msg.edit(
                content=f"პლეილისტი ჩაიტვირთა: {info.get('title', '?')} — {len(info['entries'])} სიმღერა"
            )
        except Exception as e:
            await status_msg.edit(content=f"პლეილისტის ჩატვირთვა ვერ მოხერხდა: {e}")

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

    @commands.command()
    async def play(self, ctx, *, url: str):
        if not ctx.author.voice:
            await ctx.send("ვოისში უნდა იყო შესული!")
            return

        await self.ensure_voice(ctx)
        guild_id = ctx.guild.id
        await self.guild_dao.update_last_activity(guild_id)
        self.last_text_channel[guild_id] = ctx.channel

        is_playlist = 'list=' in url or '/playlist' in url
        bare_url = url
        if 'list=' in url and 'playlist' not in url:
            bare_url = url.split('&list=')[0].split('?list=')[0]
            is_playlist = False

        status_msg = await ctx.send("ვამუშავებ...")

        resolved = await self.resolve_url_fast(bare_url)
        if not resolved:
            await status_msg.edit(content="სიმღერის ჩატვირთვა ვერ მოხერხდა")
            return

        vc = ctx.voice_client
        await self.music_dao.queue_song(guild_id, resolved)

        if vc and vc.is_playing():
            await status_msg.edit(content=f"რიგში დაემატა: {resolved.title}")
        else:
            await status_msg.edit(content=f"ვუკრავ: {resolved.title}")
            await self.play_next(ctx)

        if is_playlist:
            asyncio.create_task(self.fetch_playlist_background(ctx, url, status_msg))

    @commands.command()
    async def playlist(self, ctx, *, url: str):
        if not ctx.author.voice:
            await ctx.send("ვოისში უნდა იყო შესული!")
            return

        await self.ensure_voice(ctx)
        guild_id = ctx.guild.id
        await self.guild_dao.update_last_activity(guild_id)
        self.last_text_channel[guild_id] = ctx.channel

        processing_msg = await ctx.send("ვამუშავებ პლეილისტს...")
        vc = ctx.voice_client
        is_playing = vc and vc.is_playing()

        try:
            config = self.ytdl_config.copy()
            config['extract_flat'] = True

            with yt_dlp.YoutubeDL(config) as ydl:
                info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

            if 'entries' not in info or not info['entries']:
                await processing_msg.edit(content="პლეილისტი ვერ ვიპოვე ან ცარიელია")
                return

            entries = info['entries']
            playlist_title = info.get('title', 'Unknown Playlist')
            await processing_msg.edit(content=f"პლეილისტი ნაპოვნია: {playlist_title} - {len(entries)} სიმღერა")

            if not is_playing and entries:
                first = entries[0]
                first_song = Song(
                    url=None,
                    title=first.get('title', 'Unknown Track'),
                    original_url=first.get('webpage_url') or first.get('url')
                )
                await self.music_dao.queue_song(guild_id, first_song)
                await processing_msg.edit(content=f"ვიწყებ დაკვრას: {first_song.title}")
                await self.play_next(ctx)
                asyncio.create_task(self.load_playlist_tracks(ctx, entries[1:], len(entries), processing_msg))
            else:
                asyncio.create_task(self.load_playlist_tracks(ctx, entries, len(entries), processing_msg))

        except Exception as e:
            await processing_msg.edit(content=f"შეცდომა პლეილისტის დამუშავებისას: {str(e)}")

    async def load_playlist_tracks(self, ctx, entries, total_songs: int, status_msg):
        guild_id = ctx.guild.id
        songs_added = 0

        for i, entry in enumerate(entries):
            if not entry:
                continue
            await self.music_dao.queue_song(guild_id, Song(
                url=None,
                title=entry.get('title', 'Unknown Track'),
                original_url=entry.get('webpage_url') or entry.get('url')
            ))
            songs_added += 1
            if i % 10 == 0:
                await status_msg.edit(content=f"დამატებულია {songs_added}/{total_songs} სიმღერა...")

        await status_msg.edit(content=f"რიგში დაემატა {songs_added} სიმღერა პლეილისტიდან")

        if not ctx.voice_client.is_playing():
            await self.play_next(ctx)

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


async def setup(bot, music_dao: MusicDao, guild_dao: GuildDao):
    await bot.add_cog(MusicCog(bot, music_dao, guild_dao))
    logger.info("Music cog loaded")