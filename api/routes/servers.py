from fastapi import APIRouter, Request

router = APIRouter(prefix = "/servers", tags = ["servers"])

@router.get("")
async def get_servers(request: Request):
    bot = request.app.state.bot
    result = []
    for g in bot.guilds:
        channels = []
        for c in g.text_channels:
            channels.append({
                "id": str(c.id),
                "name": c.name
            })
        result.append({
            "id": str(g.id),
            "name": g.name,
            "member_count": g.member_count,
            "channels": channels
        })
    return result