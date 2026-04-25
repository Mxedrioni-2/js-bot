from fastapi import Request
from dao.music_dao import MusicDao
from dao.guild_dao import GuildDao

def get_daos(request: Request) -> tuple[MusicDao, GuildDao]:
    return request.app.state.music_dao, request.app.state.guild_dao