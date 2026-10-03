import hashlib
import hmac

TIMESTAMP_HEADER = "X-Jarvis-Timestamp"
SIGNATURE_HEADER = "X-Jarvis-Signature"
MAX_SKEW_SECONDS = 30
EXECUTE_PATH = "/v1/execute"
STATUS_PATH = "/v1/status"


def sign(key: str, method: str, path: str, timestamp: int, body: bytes) -> str:
    message = b"\n".join([method.upper().encode(), path.encode(), str(timestamp).encode(), hashlib.sha256(body).digest()])
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify(key: str, method: str, path: str, timestamp: int, body: bytes, signature: str, now: float) -> bool:
    if not key.strip("0"):
        return False
    if abs(now - timestamp) > MAX_SKEW_SECONDS:
        return False
    return hmac.compare_digest(sign(key, method, path, timestamp, body), signature)
