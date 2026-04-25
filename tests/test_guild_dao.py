import pytest
import time
from models.song import Song
from models.guild_state import GuildState
from tests.conftest import GUILD_ID


async def test_get_state_returns_defaults_for_new_guild(guild_dao):
    state = await guild_dao.get_state(GUILD_ID)
    assert state.loop_state == 0
    assert state.current_song is None
    assert state.volume == 1.0


async def test_set_and_get_state(guild_dao):
    song = Song(title="Now Playing", original_url="https://example.com/x")
    state = GuildState(loop_state=1, current_song=song, last_activity=time.time(), volume=0.8)
    await guild_dao.set_state(GUILD_ID, state)

    retrieved = await guild_dao.get_state(GUILD_ID)
    assert retrieved.loop_state == 1
    assert retrieved.current_song == song
    assert retrieved.volume == pytest.approx(0.8)


async def test_delete_state_resets_to_defaults(guild_dao):
    await guild_dao.set_loop_state(GUILD_ID, 2)
    await guild_dao.delete_state(GUILD_ID)
    state = await guild_dao.get_state(GUILD_ID)
    assert state.loop_state == 0


async def test_loop_state_roundtrip(guild_dao):
    for mode in (0, 1, 2):
        await guild_dao.set_loop_state(GUILD_ID, mode)
        assert await guild_dao.get_loop_state(GUILD_ID) == mode


async def test_current_song_roundtrip(guild_dao, sample_song):
    await guild_dao.set_current_song(GUILD_ID, sample_song)
    assert await guild_dao.get_current_song(GUILD_ID) == sample_song


async def test_set_current_song_to_none(guild_dao, sample_song):
    await guild_dao.set_current_song(GUILD_ID, sample_song)
    await guild_dao.set_current_song(GUILD_ID, None)
    assert await guild_dao.get_current_song(GUILD_ID) is None


async def test_update_last_activity_advances_timestamp(guild_dao):
    before = time.time()
    await guild_dao.update_last_activity(GUILD_ID)
    state = await guild_dao.get_state(GUILD_ID)
    assert state.last_activity >= before


async def test_check_inactive_returns_true_when_stale(guild_dao):
    state = GuildState(last_activity=time.time() - 300)
    await guild_dao.set_state(GUILD_ID, state)
    assert await guild_dao.check_inactive(GUILD_ID, max_interval=180) is True


async def test_check_inactive_returns_false_when_recent(guild_dao):
    await guild_dao.update_last_activity(GUILD_ID)
    assert await guild_dao.check_inactive(GUILD_ID, max_interval=180) is False


async def test_volume_roundtrip(guild_dao):
    await guild_dao.set_volume(GUILD_ID, 0.5)
    assert await guild_dao.get_volume(GUILD_ID) == pytest.approx(0.5)


async def test_state_isolated_per_guild(guild_dao):
    other = 999888777
    await guild_dao.set_loop_state(GUILD_ID, 2)
    assert await guild_dao.get_loop_state(other) == 0


async def test_state_survives_new_dao_instance(redis):
    """GuildState written by one DAO is readable by a new DAO on the same Redis client."""
    from dao.guild_dao import GuildDao
    dao1 = GuildDao(redis)
    dao2 = GuildDao(redis)

    await dao1.set_loop_state(GUILD_ID, 2)
    assert await dao2.get_loop_state(GUILD_ID) == 2
