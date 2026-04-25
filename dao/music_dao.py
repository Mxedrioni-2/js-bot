from redis.asyncio import Redis
from models.song import Song
from typing import Optional

class MusicDao:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client

    async def queue_song(self, guild_id: int, song: Song):
        await self.redis_client.rpush(f"music:guild:{guild_id}:queue", song.model_dump_json())

    async def pop_song(self, guild_id: int) -> Optional[Song]:
        song = await self.redis_client.lpop(f"music:guild:{guild_id}:queue")
        return Song.model_validate_json(song) if song else None
    
    async def peek_queue(self, guild_id: int) -> list[Song]:  # return list[Song] not list[dict]
        songs = await self.redis_client.lrange(f"music:guild:{guild_id}:queue", 0, -1)
        return [Song.model_validate_json(song) for song in songs if song]
    
    async def get_queue_length(self, guild_id: int) -> int:
        return await self.redis_client.llen(f"music:guild:{guild_id}:queue")
    
    async def exists_queue(self, guild_id: int) -> bool:
        key = f"music:guild:{guild_id}:queue"
        return await self.redis_client.exists(key)
    
    async def clear_queue(self, guild_id: int):
        await self.redis_client.delete(f"music:guild:{guild_id}:queue")

    async def remove_song(self, guild_id: int, index: int):
        tmp = "__deleted__"
        key = f"music:guild:{guild_id}:queue"
        await self.redis_client.lset(key, index, tmp)
        await self.redis_client.lrem(key, 1, tmp)
    

