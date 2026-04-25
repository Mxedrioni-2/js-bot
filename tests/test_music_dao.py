import pytest
from models.song import Song
from tests.conftest import GUILD_ID


async def test_queue_and_pop(music_dao, sample_song):
    await music_dao.queue_song(GUILD_ID, sample_song)
    popped = await music_dao.pop_song(GUILD_ID)
    assert popped == sample_song


async def test_pop_empty_queue_returns_none(music_dao):
    result = await music_dao.pop_song(GUILD_ID)
    assert result is None


async def test_queue_order_is_fifo(music_dao):
    songs = [
        Song(title=f"Song {i}", original_url=f"https://example.com/{i}")
        for i in range(3)
    ]
    for song in songs:
        await music_dao.queue_song(GUILD_ID, song)

    for expected in songs:
        assert await music_dao.pop_song(GUILD_ID) == expected


async def test_peek_does_not_consume(music_dao, sample_song):
    await music_dao.queue_song(GUILD_ID, sample_song)
    peek1 = await music_dao.peek_queue(GUILD_ID)
    peek2 = await music_dao.peek_queue(GUILD_ID)
    assert peek1 == peek2 == [sample_song]


async def test_peek_returns_all_songs(music_dao):
    songs = [Song(title=f"S{i}", original_url=f"https://example.com/{i}") for i in range(5)]
    for s in songs:
        await music_dao.queue_song(GUILD_ID, s)
    assert await music_dao.peek_queue(GUILD_ID) == songs


async def test_get_queue_length(music_dao, sample_song):
    assert await music_dao.get_queue_length(GUILD_ID) == 0
    await music_dao.queue_song(GUILD_ID, sample_song)
    assert await music_dao.get_queue_length(GUILD_ID) == 1


async def test_clear_queue(music_dao, sample_song):
    await music_dao.queue_song(GUILD_ID, sample_song)
    await music_dao.clear_queue(GUILD_ID)
    assert await music_dao.get_queue_length(GUILD_ID) == 0
    assert await music_dao.pop_song(GUILD_ID) is None


async def test_remove_song_by_index(music_dao):
    songs = [Song(title=f"S{i}", original_url=f"https://example.com/{i}") for i in range(3)]
    for s in songs:
        await music_dao.queue_song(GUILD_ID, s)

    await music_dao.remove_song(GUILD_ID, 1)
    remaining = await music_dao.peek_queue(GUILD_ID)
    assert remaining == [songs[0], songs[2]]


async def test_state_isolated_per_guild(music_dao, sample_song):
    other_guild = 999888777
    await music_dao.queue_song(GUILD_ID, sample_song)
    assert await music_dao.get_queue_length(other_guild) == 0


async def test_state_survives_new_dao_instance(redis, sample_song):
    """Queue written by one DAO instance is visible to a new instance on the same Redis."""
    from dao.music_dao import MusicDao
    dao1 = MusicDao(redis)
    dao2 = MusicDao(redis)

    await dao1.queue_song(GUILD_ID, sample_song)
    assert await dao2.peek_queue(GUILD_ID) == [sample_song]
