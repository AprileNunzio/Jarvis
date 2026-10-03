import datetime as dt
import ipaddress
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

CA_DAYS = 3650
LEAF_DAYS = 397
RENEW_BEFORE_DAYS = 30
FIXED_NAMES = ("jarvis.local", "jarvis", "localhost")


@dataclass(frozen=True)
class Material:
    ca_pem: Path
    cert: Path
    key: Path


def local_addresses() -> List[str]:
    found = {"127.0.0.1"}
    try:
        import psutil
        for entries in psutil.net_if_addrs().values():
            for entry in entries:
                if entry.family == socket.AF_INET and not entry.address.startswith("169.254."):
                    found.add(entry.address)
    except Exception:
        pass
    return sorted(found, key=lambda a: tuple(int(p) for p in a.split(".")))


def local_names() -> List[str]:
    names = list(FIXED_NAMES)
    host = socket.gethostname().strip().lower()
    if host and host not in names:
        names.append(host)
    return names


def _write(path: Path, data: bytes, mode: int) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def _name(common: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Jarvis OS"), x509.NameAttribute(NameOID.COMMON_NAME, common)])


def _private_pem(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def _make_ca(directory: Path) -> Tuple[Path, Path]:
    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(_name("Jarvis OS Local CA")).issuer_name(_name("Jarvis OS Local CA"))
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=CA_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                         key_encipherment=False, data_encipherment=False, key_agreement=False,
                                         encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    ca_pem, ca_key = directory / "ca.pem", directory / "ca.key"
    _write(ca_key, _private_pem(key), 0o600)
    _write(ca_pem, cert.public_bytes(serialization.Encoding.PEM), 0o644)
    return ca_pem, ca_key


def _load_ca(ca_pem: Path, ca_key: Path):
    cert = x509.load_pem_x509_certificate(ca_pem.read_bytes())
    key = serialization.load_pem_private_key(ca_key.read_bytes(), password=None)
    return cert, key


def _make_leaf(directory: Path, ca_cert, ca_key, names: Iterable[str], addresses: Iterable[str]) -> Tuple[Path, Path]:
    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    alt = [x509.DNSName(n) for n in names] + [x509.IPAddress(ipaddress.ip_address(a)) for a in addresses]
    cert = (x509.CertificateBuilder().subject_name(_name("Jarvis OS")).issuer_name(ca_cert.subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=LEAF_DAYS))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    cert_path, key_path = directory / "server.pem", directory / "server.key"
    _write(key_path, _private_pem(key), 0o600)
    _write(cert_path, cert.public_bytes(serialization.Encoding.PEM), 0o644)
    return cert_path, key_path


def _leaf_current(directory: Path, names: List[str], addresses: List[str]) -> bool:
    cert_path, key_path, record = directory / "server.pem", directory / "server.key", directory / "san.json"
    try:
        wanted = {"names": sorted(names), "addresses": sorted(addresses)}
        if json.loads(record.read_text(encoding="utf-8")) != wanted or not key_path.exists():
            return False
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    except (OSError, ValueError):
        return False
    return cert.not_valid_after_utc - dt.datetime.now(dt.timezone.utc) > dt.timedelta(days=RENEW_BEFORE_DAYS)


def ensure_certificates(directory: Path, names: List[str], addresses: List[str]) -> Material:
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o755)
    ca_pem, ca_key = directory / "ca.pem", directory / "ca.key"
    try:
        ca_cert, ca_private = _load_ca(ca_pem, ca_key)
        expired = ca_cert.not_valid_after_utc - dt.datetime.now(dt.timezone.utc) < dt.timedelta(days=RENEW_BEFORE_DAYS * 6)
    except (OSError, ValueError):
        expired = True
    if expired:
        ca_pem, ca_key = _make_ca(directory)
        ca_cert, ca_private = _load_ca(ca_pem, ca_key)
        (directory / "san.json").unlink(missing_ok=True)
    if not _leaf_current(directory, names, addresses):
        _make_leaf(directory, ca_cert, ca_private, names, addresses)
        _write(directory / "san.json", json.dumps({"names": sorted(names), "addresses": sorted(addresses)}).encode("utf-8"), 0o644)
    return Material(ca_pem, directory / "server.pem", directory / "server.key")
