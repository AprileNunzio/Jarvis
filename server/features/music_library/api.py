from fastapi import APIRouter
from pydantic import BaseModel
import os
import json

router = APIRouter(prefix="/api/music", tags=["Music"])
PLAYLISTS_FILE = os.path.join("data", "Musica", "playlists.json")

class Playlist(BaseModel):
    name: str
    tracks: list[str]

@router.get("/playlists")
async def get_playlists():
    if not os.path.exists(PLAYLISTS_FILE):
        return []
    with open(PLAYLISTS_FILE, "r") as f:
        return json.load(f)

@router.post("/playlists")
async def save_playlists(playlists: list[Playlist]):
    os.makedirs(os.path.dirname(PLAYLISTS_FILE), exist_ok=True)
    with open(PLAYLISTS_FILE, "w") as f:
        json.dump([p.dict() for p in playlists], f)
    return {"status": "ok"}
