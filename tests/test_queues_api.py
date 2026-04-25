import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport
from api.app import create_app
from api.auth import require_admin
from dao.music_dao import MusicDao
from dao.guild_dao import GuildDao
from models.song import Song
from tests.conftest import GUILD_ID


@pytest.fixture
def app(redis):
    music_dao = MusicDao(redis)
    guild_dao = GuildDao(redis)
    bot = MagicMock()
    bot.guilds = []
    application = create_app(bot, music_dao, guild_dao)
    application.dependency_overrides[require_admin] = lambda: {"username": "admin", "role": "admin"}
    return application


@pytest.fixture
def daos(redis):
    return MusicDao(redis), GuildDao(redis)


async def test_get_queue_empty(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/queues/{GUILD_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["guild_id"] == GUILD_ID
    assert data["queue"] == []
    assert data["current_song"] is None
    assert data["loop_state"] == "off"


async def test_get_queue_with_songs(app, daos):
    music_dao, _ = daos
    songs = [Song(title=f"Track {i}", original_url=f"https://example.com/{i}") for i in range(3)]
    for s in songs:
        await music_dao.queue_song(GUILD_ID, s)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/queues/{GUILD_ID}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["queue"]) == 3
    assert data["queue"][0]["title"] == "Track 0"
    assert data["queue"][2]["title"] == "Track 2"


async def test_get_queue_shows_current_song(app, daos, sample_song):
    _, guild_dao = daos
    await guild_dao.set_current_song(GUILD_ID, sample_song)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/queues/{GUILD_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["current_song"]["title"] == sample_song.title
    assert data["current_song"]["original_url"] == sample_song.original_url


async def test_get_queue_reflects_loop_state(app, daos):
    _, guild_dao = daos

    loop_mode_map = {0: "off", 1: "song", 2: "queue"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for mode, label in loop_mode_map.items():
            await guild_dao.set_loop_state(GUILD_ID, mode)
            response = await client.get(f"/queues/{GUILD_ID}")
            assert response.json()["loop_state"] == label


async def test_get_queue_requires_auth(redis):
    music_dao = MusicDao(redis)
    guild_dao = GuildDao(redis)
    bot = MagicMock()
    bot.guilds = []
    app = create_app(bot, music_dao, guild_dao)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/queues/{GUILD_ID}")

    assert response.status_code == 401
