from fastapi import APIRouter, Request, HTTPException
from api.utils.utils import get_daos

router = APIRouter(prefix="/queues", tags=["queues"])

@router.get("/{guild_id}")
async def get_queue(guild_id: int, request: Request):
    music_dao, guild_dao = get_daos(request)
    queue = await music_dao.peek_queue(guild_id)
    current = await guild_dao.get_current_song(guild_id)
    loop_state = await guild_dao.get_loop_state(guild_id)
    loop_modes = ["off", "song", "queue"]

    return {
        "guild_id": guild_id,
        "current_song": current.model_dump() if current else None,
        "loop_state": loop_modes[loop_state],
        "queue": [song.model_dump() for song in queue],
    }