"""
Tests for the play_next resolve optimisation: songs that already have a
stream URL (queued via !play) must not trigger a second yt-dlp call, while
songs with url=None (queued from a playlist) must still be resolved.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from models.song import Song
from tests.conftest import GUILD_ID

RESOLVED_SONG = Song(
    title="Test Song",
    original_url="https://www.youtube.com/watch?v=abc",
    url="https://stream.example.com/audio.webm",
)

PLAYLIST_SONG = Song(
    title="Playlist Song",
    original_url="https://www.youtube.com/watch?v=xyz",
    url=None,
)


def make_cog(music_dao, guild_dao):
    from cogs.music.music_cog import MusicCog
    bot = MagicMock()
    bot.guilds = []
    bot.loop = MagicMock()
    cog = MusicCog.__new__(MusicCog)
    cog.bot = bot
    cog.music_dao = music_dao
    cog.guild_dao = guild_dao
    cog.last_text_channel = {}
    cog.inactivity_timeout = 180
    cog.ffmpeg_config = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }
    return cog


def make_ctx(guild_id=GUILD_ID):
    ctx = MagicMock()
    ctx.guild.id = guild_id
    ctx.voice_client = MagicMock()
    ctx.voice_client.play = MagicMock()
    ctx.send = AsyncMock()
    return ctx


async def test_play_next_skips_resolve_when_url_set(music_dao, guild_dao):
    """Song with url already set must not call resolve_url."""
    await music_dao.queue_song(GUILD_ID, RESOLVED_SONG)
    cog = make_cog(music_dao, guild_dao)
    cog.resolve_url = AsyncMock(return_value=RESOLVED_SONG)

    with patch("discord.FFmpegOpusAudio.from_probe", new_callable=AsyncMock) as mock_probe:
        mock_probe.return_value = MagicMock()
        await cog.play_next(make_ctx())

    cog.resolve_url.assert_not_called()


async def test_play_next_resolves_when_url_is_none(music_dao, guild_dao):
    """Song with url=None (playlist entry) must be resolved before playing."""
    await music_dao.queue_song(GUILD_ID, PLAYLIST_SONG)
    cog = make_cog(music_dao, guild_dao)
    cog.resolve_url = AsyncMock(return_value=RESOLVED_SONG)

    with patch("discord.FFmpegOpusAudio.from_probe", new_callable=AsyncMock) as mock_probe:
        mock_probe.return_value = MagicMock()
        await cog.play_next(make_ctx())

    cog.resolve_url.assert_called_once_with(PLAYLIST_SONG.original_url)


async def test_play_next_empty_queue_does_nothing(music_dao, guild_dao):
    cog = make_cog(music_dao, guild_dao)
    cog.resolve_url = AsyncMock()
    ctx = make_ctx()

    await cog.play_next(ctx)

    cog.resolve_url.assert_not_called()
    ctx.send.assert_not_called()
