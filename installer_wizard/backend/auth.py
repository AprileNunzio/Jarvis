import base64
import hashlib
import hmac
import secrets
import time

from config import DEMO, ETC_DIR

SESSION_COOKIE = "jarvis_session"
SESSION_TTL = 12 * 3600
ADMIN_GROUPS = {"sudo", "wheel", "jarvis-admin"}
_SECRET_FILE = ETC_DIR / "session.key"
_failures: dict = {}


def _secret() -> bytes:
    if not _SECRET_FILE.exists():
        _SECRET_FILE.write_bytes(secrets.token_bytes(32))
        _SECRET_FILE.chmod(0o600)
    return _SECRET_FILE.read_bytes()


def _is_admin_user(username: str) -> bool:
    if username == "root":
        return True
    import grp
    import pwd
    try:
        primary = grp.getgrgid(pwd.getpwnam(username).pw_gid).gr_name
    except KeyError:
        return False
    groups = {g.gr_name for g in grp.getgrall() if username in g.gr_mem} | {primary}
    return bool(groups & ADMIN_GROUPS)


def rate_limited(ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _failures.get(ip, []) if now - t < 300]
    _failures[ip] = attempts
    return len(attempts) >= 5


def authenticate(username: str, password: str, ip: str) -> bool:
    if rate_limited(ip):
        return False
    ok = False
    if DEMO:
        ok = username == "admin" and password == "jarvis"
    elif username and password:
        import pam
        ok = pam.pam().authenticate(username, password, service="jarvis-admin") and _is_admin_user(username)
    if not ok:
        _failures.setdefault(ip, []).append(time.time())
    return ok


def issue(username: str) -> str:
    payload = f"{username}|{int(time.time()) + SESSION_TTL}"
    sig = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode()


def verify(token: str | None) -> str | None:
    if not token:
        return None
    try:
        username, expires, sig = base64.urlsafe_b64decode(token.encode()).decode().rsplit("|", 2)
    except (ValueError, UnicodeDecodeError):
        return None
    expected = hmac.new(_secret(), f"{username}|{expires}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected) or int(expires) < time.time():
        return None
    return username
