import os
import shutil
import asyncio
import logging
try:
    import mutagen
    from mutagen.easyid3 import EasyID3
except ImportError:
    mutagen = None
    EasyID3 = None

logger = logging.getLogger("jarvis.music_library")

# Rileva automaticamente se il server ha il disco Y: mappato
MUSIC_ROOT = "Y:\\Musica" if os.path.exists("Y:\\") else os.path.join("data", "Musica")
UNSORTED_DIR = os.path.join(MUSIC_ROOT, "Nuova_Musica")
LIBRARY_DIR = os.path.join(MUSIC_ROOT, "Libreria")

class MusicAutoOrganizer:
    def __init__(self):
        self._running = False
        os.makedirs(UNSORTED_DIR, exist_ok=True)
        os.makedirs(LIBRARY_DIR, exist_ok=True)

    def extract_metadata(self, file_path: str) -> dict:
        artist = "Sconosciuto"
        title = os.path.basename(file_path)
        album = "Singoli"
        
        if mutagen and file_path.lower().endswith('.mp3'):
            try:
                tags = EasyID3(file_path)
                artist = tags.get("artist", [artist])[0]
                title = tags.get("title", [title])[0]
                album = tags.get("album", [album])[0]
            except Exception:
                pass
                
        # Estrazione base dal nome file se i tag falliscono
        if artist == "Sconosciuto" and " - " in title:
            parts = title.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].rsplit(".", 1)[0].strip()
            
        return {"artist": artist, "title": title, "album": album}

    def process_file(self, file_path: str):
        meta = self.extract_metadata(file_path)
        artist = meta["artist"].replace("/", "_").replace("\\", "_")
        album = meta["album"].replace("/", "_").replace("\\", "_")
        
        dest_dir = os.path.join(LIBRARY_DIR, artist, album)
        os.makedirs(dest_dir, exist_ok=True)
        
        filename = os.path.basename(file_path)
        dest_path = os.path.join(dest_dir, filename)
        
        shutil.move(file_path, dest_path)
        logger.info(f"Brano organizzato: {artist} - {meta['title']}")
        
        if "ac/dc" in artist.lower() and "back in black" in meta["title"].lower():
            logger.info("ROCK ON! Trovato Back in Black degli AC/DC, la mia canzone preferita in assoluto! Aggiunta alla libreria d'onore.")

    async def scan_loop(self):
        self._running = True
        logger.info("Music Auto-Organizer avviato. In attesa di file in data/Musica/Nuova_Musica...")
        while self._running:
            try:
                for filename in os.listdir(UNSORTED_DIR):
                    if filename.startswith("."):
                        continue
                    file_path = os.path.join(UNSORTED_DIR, filename)
                    if os.path.isfile(file_path) and filename.lower().endswith(('.mp3', '.flac', '.wav', '.m4a')):
                        self.process_file(file_path)
            except Exception as e:
                logger.error(f"Errore nello scan musicale: {e}")
            await asyncio.sleep(60)  # Controlla ogni minuto

music_organizer = MusicAutoOrganizer()
