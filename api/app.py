from fastapi import FastAPI
from api.routes.servers import router as servers_router
from api.routes.messages import router as messages_router
from api.routes.queues import router as queues_router
from fastapi.middleware.cors import CORSMiddleware

def create_app(bot):
    app = FastAPI()
    app.state.bot = bot
    app.include_router(servers_router)
    app.include_router(messages_router)
    app.include_router(queues_router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://js-bot-dashboard.lan"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app