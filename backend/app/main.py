from fastapi import FastAPI

from app.api import assets, clips, health, music, settings, system, tasks, upload

app = FastAPI(
    title="Live Stream AI Clipper",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(settings.router)
app.include_router(upload.router)
app.include_router(tasks.router)
app.include_router(clips.router)
app.include_router(music.router)
app.include_router(assets.router)
app.include_router(system.router)
