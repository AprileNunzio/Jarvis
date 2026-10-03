import secrets
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class ServerSettings(BaseSettings):
    JARVIS_ENV: Literal["development", "production", "testing"] = "development"
    JARVIS_HOST: str = "0.0.0.0"
    JARVIS_PORT: int = 8443
    JARVIS_SECRET_KEY: str = "0000000000000000000000000000000000000000000000000000000000000000"
    DATA_DIR: str = "./data"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    JARVIS_LLM_MODEL: str = ""
    JARVIS_LLM_FAST_MODEL: str = ""
    JARVIS_LLM_CHAT_ORDER: str = ""
    JARVIS_LLM_DEEP_ORDER: str = ""
    JARVIS_LLM_RICERCATORE_ORDER: str = ""
    JARVIS_LLM_DOMOTICO_ORDER: str = ""
    JARVIS_LLM_STUDIO_ORDER: str = ""
    JARVIS_LLM_CODER_ORDER: str = ""
    JARVIS_LLM_3D_ORDER: str = ""
    JARVIS_EMBED_MODEL: str = "nomic-embed-text"
    JARVIS_ASSISTANT_NAME: str = ""
    JARVIS_USER_NAME: str = ""
    HOME_ASSISTANT_URL: str = "http://127.0.0.1:8123"
    HOME_ASSISTANT_TOKEN: str = ""
    FRIGATE_URL: str = "http://127.0.0.1:5000"
    CODE_SANDBOX_TIMEOUT_SECONDS: int = 30
    SANDBOX_SOCKET_PATH: str = "/run/jarvis/sandbox/broker.sock"
    BRAIN_ROUTES_PATH: str = "/run/jarvis/brain/routes.json"
    JARVIS_SUPERVISOR_URL: str = "http://127.0.0.1:8080"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = ServerSettings()
if not settings.JARVIS_SECRET_KEY.strip("0"):
    settings.JARVIS_SECRET_KEY = secrets.token_hex(32)
