from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import logging

router = APIRouter(prefix = "/messages", tags = ["messages"])

logger = logging.getLogger(__name__)

class MessageRequest(BaseModel):
    channel_id: str
    message: str

@router.post("")
async def send_message(req: MessageRequest, request: Request):
    bot = request.app.state.bot
    logger.info(f"Looking for channel: {req.channel_id}")
    logger.info(f"Available channels: {[c.id for g in bot.guilds for c in g.text_channels]}")
    channel = bot.get_channel(int(req.channel_id))
    if not channel:
        raise HTTPException(status_code=404, detail = f"channel with id {req.channel_id} not found")
    await channel.send(req.message)
    return {"ok": True}