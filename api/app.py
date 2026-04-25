from fastapi import FastAPI, Depends
from api.routes.servers import router as servers_router
from api.routes.messages import router as messages_router
from api.routes.queues import router as queues_router
from api.routes.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from api.auth import require_admin
from dotenv import load_dotenv
import os
from dao.music_dao import MusicDao
from dao.guild_dao import GuildDao

load_dotenv()

env = os.environ.get("ENV", "DEV")

allowed_origins = ["http://js-bot-dashboard.lan"] if env != "DEV" else ["*"]

def create_app(bot, music_dao: MusicDao, guild_dao: GuildDao):
    app = FastAPI()
    app.state.bot = bot
    app.state.music_dao = music_dao
    app.state.guild_dao = guild_dao
    app.include_router(auth_router) 
    app.include_router(servers_router, dependencies = [Depends(require_admin)])
    app.include_router(messages_router, dependencies = [Depends(require_admin)])
    app.include_router(queues_router, dependencies = [Depends(require_admin)])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app