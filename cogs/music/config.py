YTDL_CONFIG = {
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

FFMPEG_CONFIG = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -ar 48000 -ac 2 -b:a 128k -bufsize 4096k',
}

INACTIVITY_TIMEOUT = 180
