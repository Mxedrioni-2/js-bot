from discord.ext import commands, tasks
import yt_dlp
import discord
from collections import deque
import asyncio
import time

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {} 
        self.inactivity_timeout = 180
        self.last_activity = {}
        self.last_text_channel = {}
        self.loop_state = {}
        self.current_song = {}
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

    def update_activity(self, guild_id):
        self.last_activity[guild_id] = time.time()

    @tasks.loop(seconds=180)
    async def check_inactivity(self):
        for guild_id, last_active_time in dict(self.last_activity).items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            vc = guild.voice_client
            if vc and vc.is_connected():
                current_time = time.time()
                if ((current_time - self.last_activity[guild_id] > self.inactivity_timeout) and not vc.is_playing()) or self.vc_is_empty(vc):
                    await vc.disconnect()
                    if guild_id in self.queues:
                        self.queues[guild_id].clear()
                    if guild_id in self.loop_state:
                        del self.loop_state[guild_id]
                    if guild_id in self.current_song:
                        del self.current_song[guild_id]
                    del self.last_activity[guild_id]
                    try:
                        await self.last_text_channel[guild_id].send("კაი კაი აღარ მცალია გერმანიაში მაქვს ფრენა საოპერაციოდ, ყლეზე მკიდია ეგ მარადიული ცხოვრება და სიკვდილი")
                    except discord.Forbidden:
                        continue

    @check_inactivity.before_loop
    async def before_check_inactivity(self):
        await self.bot.wait_until_ready()
    
    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        return self.queues[guild_id]
    
    def get_loop_state(self, guild_id):
        if guild_id not in self.loop_state:
            self.loop_state[guild_id] = 0
        return self.loop_state[guild_id]

    async def play_next(self, ctx):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        loop_state = self.get_loop_state(guild_id)
        
        if loop_state == 1 and guild_id in self.current_song:
            next_song = self.current_song[guild_id]
        elif queue:
            if loop_state == 2 and guild_id in self.current_song:
                if not queue:
                    next_song = self.current_song[guild_id]
                else:
                    next_song = queue.popleft()
                    if guild_id in self.current_song:
                        queue.append(self.current_song[guild_id])
            else:
                next_song = queue.popleft()
            
            self.current_song[guild_id] = next_song
        else:
            return
        
        try:
            source = await discord.FFmpegOpusAudio.from_probe(
                next_song['url'],
                **self.ffmpeg_config,
                method='fallback'
            )
            
            def after_playing(error):
                if error:
                    print(f"დამენძრა: {error}")
                    self.last_activity[guild_id] = time.time()
                asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop)
            
            ctx.voice_client.play(source, after=after_playing)
            
            loop_msg = " (ლუპში)" if loop_state == 1 else ""
            await ctx.send(f'ახლა ვუკრავ: {next_song["title"]}{loop_msg}')
            
        except Exception as e:
            await ctx.send(f"დამენძრა: {str(e)}")
            await self.play_next(ctx)
    
    async def process_url(self, url, download=False):
        quick_config = self.ytdl_config.copy()
        try:
            with yt_dlp.YoutubeDL(quick_config) as ydl:
                info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(url, download=download))
                
                if 'entries' in info:
                    if not info['entries']:
                        return None, [], False
                    
                    is_playlist = len(info['entries']) > 1
                    if is_playlist:
                        entries = []
                        for entry in info['entries']:
                            if entry:
                                entries.append({
                                    'url': entry.get('url'),
                                    'title': entry.get('title', 'Unknown Track')
                                })
                        return info.get('title', 'Unknown Playlist'), entries, True
                    else:
                        info = info['entries'][0]
                
                return info.get('title', 'Unknown Track'), {
                    'url': info.get('url'),
                    'title': info.get('title', 'Unknown Track')
                }, False
                
        except Exception as e:
            print(f"Error processing URL: {e}")
            return None, None, False

    @commands.command()
    async def play(self, ctx, *, url):
        if not ctx.author.voice:
            await ctx.send("ვოისში უნდა იყო შესული!")
            return

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()

        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
            
        self.update_activity(guild_id)
        self.last_text_channel[guild_id] = ctx.channel
        
        if guild_id not in self.loop_state:
            self.loop_state[guild_id] = 0
        
        processing_msg = await ctx.send("ვამუშავებ სიმღერას...")
        is_playing = voice_client and voice_client.is_playing()
        
        is_likely_playlist = 'list=' in url and 'playlist' not in url.lower()
        playlist_requested = 'playlist' in url.lower() or is_likely_playlist
        
        try:
            if is_likely_playlist and not playlist_requested:
                url = url.split('&list=')[0] if '&list=' in url else url.split('?list=')[0] if '?list=' in url else url
                playlist_requested = False
            
            title, result, is_playlist = await self.process_url(url)
            queue = self.get_queue(guild_id)
            
            if is_playlist:
                await processing_msg.edit(content=f"პლეილისტი ნაპოვნია: {title} - {len(result)} სიმღერა")
                
                for song_info in result:
                    queue.append(song_info)
                
                await ctx.send(f"რიგში დაემატა {len(result)} სიმღერა პლეილისტიდან")
                
                if not is_playing and result:
                    await self.play_next(ctx)
            
            elif result:
                song_info = result
                
                if is_playing:
                    queue.append(song_info)
                    position = len(queue)
                    await processing_msg.edit(content=f'{position}: {song_info["title"]} დაემატა რიგში')
                else:
                    queue.append(song_info)
                    await processing_msg.edit(content=f'ვიწყებ დაკვრას: {song_info["title"]}')
                    await self.play_next(ctx)
            else:
                await processing_msg.edit(content="სიმღერის დამუშავება ვერ მოხერხდა")
                
        except Exception as e:
            await processing_msg.edit(content=f"დამენძრა: {str(e)}")

    @commands.command()
    async def playlist(self, ctx, *, url):
        if not ctx.author.voice:
            await ctx.send("ვოისში უნდა იყო შესული!")
            return

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()

        voice_client = ctx.voice_client
        guild_id = ctx.guild.id
            
        self.update_activity(guild_id)
        self.last_text_channel[guild_id] = ctx.channel
        
        if guild_id not in self.loop_state:
            self.loop_state[guild_id] = 0
            
        processing_msg = await ctx.send("ვამუშავებ პლეილისტს...")
        is_playing = voice_client and voice_client.is_playing()
        
        try:
            quick_config = self.ytdl_config.copy()
            quick_config['extract_flat'] = True
            
            with yt_dlp.YoutubeDL(quick_config) as ydl:
                info = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                
                if 'entries' not in info or not info['entries']:
                    await processing_msg.edit(content="პლეილისტი ვერ ვიპოვე ან ცარიელია")
                    return
                
                queue = self.get_queue(guild_id)
                playlist_title = info.get('title', 'Unknown Playlist')
                total_songs = len(info['entries'])
                
                await processing_msg.edit(content=f"პლეილისტი ნაპოვნია: {playlist_title} - {total_songs} სიმღერა")
                
                if info['entries'] and not is_playing:
                    first_entry = info['entries'][0]
                    if first_entry:
                        try:
                            with yt_dlp.YoutubeDL(self.ytdl_config) as first_ydl:
                                first_info = await self.bot.loop.run_in_executor(None, 
                                    lambda: first_ydl.extract_info(first_entry['url'], download=False))
                                
                            first_song = {
                                'url': first_info.get('url'),
                                'title': first_info.get('title', 'First Track')
                            }
                            
                            queue.append(first_song)
                            
                            await processing_msg.edit(content=f"ვიწყებ დაკვრას: {first_song['title']}")
                            await self.play_next(ctx)
                            
                            asyncio.create_task(self.load_playlist_tracks(ctx, info['entries'][1:], total_songs, processing_msg))
                            return
                            
                        except Exception as e:
                            print(f"Error with first track: {e}")
                
                await self.load_playlist_tracks(ctx, info['entries'], total_songs, processing_msg)
                
        except Exception as e:
            await processing_msg.edit(content=f"შეცდომა პლეილისტის დამუშავებისას: {str(e)}")
    
    async def load_playlist_tracks(self, ctx, entries, total_songs, status_msg):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        is_playing = ctx.voice_client and ctx.voice_client.is_playing()
        
        songs_added = 0
        batch_size = 10
        
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i+batch_size]
            batch_tasks = []
            
            for entry in batch:
                if not entry:
                    continue
                    
                task = self.process_playlist_entry(entry)
                batch_tasks.append(task)
            
            results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    continue
                    
                if result:
                    queue.append(result)
                    songs_added += 1
            
            await status_msg.edit(content=f"დამატებულია {songs_added}/{total_songs} სიმღერა პლეილისტიდან...")
        
        await status_msg.edit(content=f"რიგში დაემატა {songs_added} სიმღერა პლეილისტიდან")
        
        if not is_playing and songs_added > 0 and not ctx.voice_client.is_playing():
            await self.play_next(ctx)
    
    async def process_playlist_entry(self, entry):
        try:
            quick_config = {
                'format': 'bestaudio/best',
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(quick_config) as ydl:
                info = await self.bot.loop.run_in_executor(None, 
                       lambda: ydl.extract_info(entry['url'], download=False))
                
                return {
                    'url': info.get('url'),
                    'title': info.get('title', 'Unknown Track')
                }
                
        except Exception as e:
            print(f"Error processing playlist entry: {e}")
            return None

    @commands.command()
    async def loop(self, ctx, mode="show"):
        guild_id = ctx.guild.id
        
        if guild_id not in self.loop_state:
            self.loop_state[guild_id] = 0
        
        self.update_activity(guild_id)
        self.last_text_channel[guild_id] = ctx.channel
        
        if mode.lower() == "show":
            loop_modes = ["გამორთული", "ერთი სიმღერა", "რიგი"]
            current_mode = self.loop_state[guild_id]
            await ctx.send(f"ლუპის რეჟიმი: {loop_modes[current_mode]}")
            return
            
        if mode.lower() in ["off", "გამორთვა", "0"]:
            self.loop_state[guild_id] = 0
            await ctx.send("ლუპი გამორთულია")
        elif mode.lower() in ["song", "current", "სიმღერა", "1"]:
            self.loop_state[guild_id] = 1
            await ctx.send("ლუპი: მიმდინარე სიმღერა")
        elif mode.lower() in ["queue", "all", "რიგი", "2"]:
            self.loop_state[guild_id] = 2
            await ctx.send("ლუპი: მთლიანი რიგი")
        else:
            await ctx.send("არასწორი რეჟიმი. გამოიყენე: `!loop off`, `!loop song`, ან `!loop queue`")

    @commands.command()
    async def stop(self, ctx):
        if ctx.voice_client:
            guild_id = ctx.guild.id
            if guild_id in self.queues:
                self.queues[guild_id].clear()
            
            if guild_id in self.loop_state:
                self.loop_state[guild_id] = 0
            
            if guild_id in self.current_song:
                del self.current_song[guild_id]
                
            await ctx.voice_client.disconnect()
            await ctx.send("მოვრჩი დაკვრას, კაი კაი აღარ მცალია გერმანიაში მაქვს ფრენა საოპერაციოდ, ყლეზე მკიდია ეგ მარადიული ცხოვრება და სიკვდილი")

    @commands.command()
    async def skip(self, ctx):
        guild_id = ctx.guild.id
        if ctx.voice_client and ctx.voice_client.is_playing():
            if self.get_loop_state(guild_id) == 1:
                self.loop_state[guild_id] = 0
                await ctx.send("სიმღერის ლუპი გამორთულია.")
            
            ctx.voice_client.stop()
            await ctx.send("დავსკიპე")
        else:
            await ctx.send("არ არის სიმღერა გაშვებული")

    @commands.command()
    async def queue(self, ctx):
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        loop_state = self.get_loop_state(guild_id)
        
        loop_modes = ["გამორთული", "სიმღერა", "რიგი"]
        loop_info = f"ლუპის რეჟიმი: {loop_modes[loop_state]}"
        
        if ctx.voice_client and ctx.voice_client.is_playing() and guild_id in self.current_song:
            current = f"ახლა უკრავს: {self.current_song[guild_id]['title']}"
        else:
            current = "არ არის სიმღერა გაშვებული"
        
        if not queue:
            await ctx.send(f"{current}\n{loop_info}\nრიგი ცარიელია")
            return

        queue_list = []
        for i, song in enumerate(queue, 1):
            queue_list.append(f"{i}. {song['title']}")
        
        queue_text = "\n".join(queue_list)
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
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        queue.clear()
        
        await ctx.send("რიგის გაწმენდა")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            guild_id = message.guild.id
            self.last_activity[guild_id] = time.time()
            self.last_text_channel[guild_id] = message.channel
        
    def vc_is_empty(self, vc):
        if not vc or not vc.channel:
            return True
        
        members = [member for member in vc.channel.members 
              if not member.bot]
        return len(members) == 0

async def setup(bot):
    await bot.add_cog(MusicCog(bot))