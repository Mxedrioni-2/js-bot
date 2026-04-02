from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/queues", tags=["queues"])

def get_music_cog(request: Request):
    cog = request.app.state.bot.cogs.get("MusicCog")
    if not cog:
        raise HTTPException(status_code=503, detail="MusicCog is not loaded")
    return cog

@router.get("/{guild_id}")
async def get_queue(guild_id: int, request: Request):
    cog = get_music_cog(request)
    queue = cog.queues.get(guild_id, [])
    current = cog.current_song.get(guild_id)
    loop_modes = ["off", "song", "queue"]

    return {
        "guild_id": guild_id,
        "current_song": current,
        "loop_state": loop_modes[cog.loop_state.get(guild_id, 0)],
        "queue": list(queue),
    }