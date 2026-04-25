import pytest
import fakeredis.aioredis
from dao.music_dao import MusicDao
from dao.guild_dao import GuildDao
from models.song import Song

GUILD_ID = 111222333


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def music_dao(redis):
    return MusicDao(redis)


@pytest.fixture
def guild_dao(redis):
    return GuildDao(redis)


@pytest.fixture
def sample_song():
    return Song(
        title="Test Song",
        original_url="https://www.youtube.com/watch?v=abc123",
        url="https://stream.example.com/audio.webm",
    )
