from dataclasses import dataclass
from typing import Final

@dataclass(frozen=True)
class SecurityConfig:
    TOKEN_EXPIRATION_MINUTES: Final[int] = 1440

security_config = SecurityConfig()
