import datetime
import hmac
import hashlib
import json
import base64
from typing import Any, Dict
from server.config.env import settings
from server.config.security import security_config
from server.shared.errors.domain_errors import UnauthorizedException

class TokenProvider:
    def __init__(self, secret_key: str = settings.JARVIS_SECRET_KEY):
        self._secret = secret_key.encode("utf-8")

    def issue_token(self, subject: str, claims: Dict[str, Any]) -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = now + datetime.timedelta(minutes=security_config.TOKEN_EXPIRATION_MINUTES)
        payload = {
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "claims": claims
        }
        raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        b64_payload = base64.urlsafe_b64encode(raw_payload).decode("utf-8").rstrip("=")
        signature = hmac.new(self._secret, b64_payload.encode("utf-8"), hashlib.sha256).digest()
        b64_signature = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
        return f"v1.local.{b64_payload}.{b64_signature}"

    def verify_token(self, token: str) -> Dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 4 or parts[0] != "v1" or parts[1] != "local":
            raise UnauthorizedException("Invalid token format")
        b64_payload, b64_signature = parts[2], parts[3]
        expected_sig = hmac.new(self._secret, b64_payload.encode("utf-8"), hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")
        if not hmac.compare_digest(b64_signature, expected_b64):
            raise UnauthorizedException("Tampered token signature")
        padding = "=" * (-len(b64_payload) % 4)
        raw_payload = base64.urlsafe_b64decode((b64_payload + padding).encode("utf-8"))
        payload_dict = json.loads(raw_payload.decode("utf-8"))
        now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        if payload_dict.get("exp", 0) < now_ts:
            raise UnauthorizedException("Expired authentication token")
        return payload_dict

token_provider = TokenProvider()
