import logging
from redis.asyncio import Redis
from models.song import Song
from typing import Optional

logger = logging.getLogger(__name__)


class MusicDao:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client

    def _key(self, guild_id: int) -> str:
        return f"music:guild:{guild_id}:queue"

    async def queue_song(self, guild_id: int, song: Song):
        await self.redis_client.rpush(self._key(guild_id), song.model_dump_json())
        logger.debug("Guild %d: queued '%s'", guild_id, song.title)

    async def pop_song(self, guild_id: int) -> Optional[Song]:
        raw = await self.redis_client.lpop(self._key(guild_id))
        if not raw:
            logger.debug("Guild %d: queue empty", guild_id)
            return None
        song = Song.model_validate_json(raw)
        logger.debug("Guild %d: popped '%s'", guild_id, song.title)
        return song

    async def peek_queue(self, guild_id: int) -> list[Song]:
        songs = await self.redis_client.lrange(self._key(guild_id), 0, -1)
        return [Song.model_validate_json(s) for s in songs if s]

    async def get_queue_length(self, guild_id: int) -> int:
        return await self.redis_client.llen(self._key(guild_id))

    async def exists_queue(self, guild_id: int) -> bool:
        return await self.redis_client.exists(self._key(guild_id))

    async def clear_queue(self, guild_id: int):
        await self.redis_client.delete(self._key(guild_id))
        logger.debug("Guild %d: queue cleared", guild_id)

    async def remove_song(self, guild_id: int, index: int):
        tmp = "__deleted__"
        key = self._key(guild_id)
        await self.redis_client.lset(key, index, tmp)
        await self.redis_client.lrem(key, 1, tmp)
        logger.debug("Guild %d: removed song at index %d", guild_id, index)
