import logging
import time
from redis.asyncio import Redis
from models.guild_state import GuildState
from models.song import Song
from typing import Optional

logger = logging.getLogger(__name__)


class GuildDao:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client

    def get_guild_state_key(self, guild_id):
        return f"music:guild:{guild_id}:state"

    async def set_state(self, guild_id: int, guild_state: GuildState):
        await self.redis_client.set(
            self.get_guild_state_key(guild_id),
            guild_state.model_dump_json(),
            ex=3600
        )

    async def get_state(self, guild_id: int) -> GuildState:
        raw = await self.redis_client.get(self.get_guild_state_key(guild_id))
        return GuildState.model_validate_json(raw) if raw else GuildState()

    async def delete_state(self, guild_id: int):
        await self.redis_client.delete(self.get_guild_state_key(guild_id))
        logger.debug("Guild %d: state deleted", guild_id)

    async def update_last_activity(self, guild_id: int):
        cur_state = await self.get_state(guild_id)
        cur_state.last_activity = time.time()
        await self.set_state(guild_id, cur_state)
        logger.debug("Guild %d: last_activity updated", guild_id)

    async def check_inactive(self, guild_id: int, max_interval: float) -> bool:
        cur_state = await self.get_state(guild_id)
        elapsed = time.time() - cur_state.last_activity
        inactive = elapsed > max_interval
        logger.debug("Guild %d: inactive check — elapsed=%.0fs limit=%.0fs result=%s",
                     guild_id, elapsed, max_interval, inactive)
        return inactive

    async def get_loop_state(self, guild_id: int) -> int:
        return (await self.get_state(guild_id)).loop_state

    async def set_loop_state(self, guild_id: int, loop_mode: int):
        cur_state = await self.get_state(guild_id)
        cur_state.loop_state = loop_mode
        await self.set_state(guild_id, cur_state)
        logger.debug("Guild %d: loop_state set to %d", guild_id, loop_mode)

    async def get_current_song(self, guild_id: int) -> Optional[Song]:
        return (await self.get_state(guild_id)).current_song

    async def set_current_song(self, guild_id: int, song: Optional[Song]):
        cur_state = await self.get_state(guild_id)
        cur_state.current_song = song
        await self.set_state(guild_id, cur_state)
        logger.debug("Guild %d: current_song set to '%s'",
                     guild_id, song.title if song else None)

    async def set_volume(self, guild_id: int, volume: float):
        cur_state = await self.get_state(guild_id)
        cur_state.volume = volume
        await self.set_state(guild_id, cur_state)
        logger.debug("Guild %d: volume set to %.2f", guild_id, volume)

    async def get_volume(self, guild_id: int) -> float:
        return (await self.get_state(guild_id)).volume
