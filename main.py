import uvicorn
from fastapi.middleware.cors import CORSMiddleware

from classes import Settings
from routers import CustomFastAPI, create_app, add_to_app, api, admin_api, guild_api, user_api

# init settings
settings = Settings("settings.json")

# FastAPI setup
app: CustomFastAPI = create_app(settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.credentials.origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
app.include_router(api)
app.include_router(admin_api)
app.include_router(guild_api)
app.include_router(user_api)

server = uvicorn.Server(uvicorn.Config(app))

add_to_app(app, server)

if __name__ == "__main__":
    server.run()
