import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

import auth
import tls
from features.ear import proxy


class CertificateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name) / "tls"

    def leaf(self):
        return x509.load_pem_x509_certificate((self.dir / "server.pem").read_bytes())

    def test_leaf_is_signed_by_the_local_ca_and_names_every_address(self):
        material = tls.ensure_certificates(self.dir, ["jarvis.local", "casa"], ["127.0.0.1", "192.168.1.5"])
        ca = x509.load_pem_x509_certificate(material.ca_pem.read_bytes())
        leaf = self.leaf()
        ca.public_key().verify(leaf.signature, leaf.tbs_certificate_bytes, ec.ECDSA(hashes.SHA256()))
        san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        self.assertEqual(sorted(san.get_values_for_type(x509.DNSName)), ["casa", "jarvis.local"])
        self.assertEqual(sorted(str(a) for a in san.get_values_for_type(x509.IPAddress)), ["127.0.0.1", "192.168.1.5"])
        self.assertTrue(ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
        self.assertFalse(leaf.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)

    def test_certificates_carry_the_key_identifiers_strict_clients_require(self):
        tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1"])
        leaf = self.leaf()
        ca = x509.load_pem_x509_certificate((self.dir / "ca.pem").read_bytes())
        aki = leaf.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier).value.key_identifier
        self.assertEqual(aki, ca.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value.digest)
        leaf.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)

    def test_second_run_changes_nothing(self):
        tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1"])
        before = {f: (self.dir / f).read_bytes() for f in ("ca.pem", "server.pem", "server.key")}
        tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1"])
        self.assertEqual(before, {f: (self.dir / f).read_bytes() for f in before})

    def test_new_address_reissues_the_leaf_but_keeps_the_ca(self):
        tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1"])
        ca, leaf = (self.dir / "ca.pem").read_bytes(), (self.dir / "server.pem").read_bytes()
        tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1", "10.0.0.9"])
        self.assertEqual(ca, (self.dir / "ca.pem").read_bytes())
        self.assertNotEqual(leaf, (self.dir / "server.pem").read_bytes())

    def test_a_leaf_close_to_expiry_is_renewed(self):
        tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1"])
        before = (self.dir / "server.pem").read_bytes()
        original = tls.RENEW_BEFORE_DAYS
        tls.RENEW_BEFORE_DAYS = 10 ** 5
        try:
            tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1"])
        finally:
            tls.RENEW_BEFORE_DAYS = original
        self.assertNotEqual(before, (self.dir / "server.pem").read_bytes())

    def test_corrupt_material_is_replaced_not_fatal(self):
        tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1"])
        (self.dir / "ca.pem").write_text("garbage")
        material = tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1"])
        self.assertTrue(material.ca_pem.read_bytes().startswith(b"-----BEGIN CERTIFICATE"))

    @unittest.skipIf(os.name == "nt", "permessi POSIX")
    def test_private_keys_are_not_readable_by_others(self):
        tls.ensure_certificates(self.dir, ["a"], ["127.0.0.1"])
        for name in ("ca.key", "server.key"):
            self.assertEqual((self.dir / name).stat().st_mode & 0o077, 0)

    def test_local_addresses_always_include_loopback(self):
        self.assertIn("127.0.0.1", tls.local_addresses())
        self.assertIn("jarvis.local", tls.local_names())


class FakeClient:
    def __init__(self, incoming):
        self.incoming, self.sent = list(incoming), []

    async def receive(self):
        if self.incoming:
            await asyncio.sleep(0)
            return self.incoming.pop(0)
        await asyncio.sleep(0.05)
        return {"type": "websocket.disconnect"}

    async def send_bytes(self, data):
        self.sent.append(data)

    async def send_text(self, text):
        self.sent.append(text)


class FakeUpstream:
    def __init__(self, replies):
        self.replies, self.received = list(replies), []

    async def send(self, message):
        self.received.append(message)

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for reply in self.replies:
            await asyncio.sleep(0.01)
            yield reply
        await asyncio.sleep(5)


class ProxyTest(unittest.IsolatedAsyncioTestCase):
    async def test_audio_and_control_flow_both_ways(self):
        client = FakeClient([{"type": "websocket.receive", "text": '{"type":"client"}'},
                             {"type": "websocket.receive", "bytes": b"\x00\x01"}])
        upstream = FakeUpstream(['{"type":"state"}', b"\x05"])
        await asyncio.wait_for(proxy.pump(client, upstream), 2)
        self.assertEqual(upstream.received, ['{"type":"client"}', b"\x00\x01"])
        self.assertEqual(client.sent, ['{"type":"state"}', b"\x05"])

    async def test_closing_the_browser_ends_the_pump(self):
        await asyncio.wait_for(proxy.pump(FakeClient([]), FakeUpstream([])), 2)

    def socket(self, host, cookie=None):
        return SimpleNamespace(client=SimpleNamespace(host=host), cookies={auth.SESSION_COOKIE: cookie} if cookie else {})

    def test_only_local_or_logged_in_sockets_are_accepted(self):
        self.assertTrue(proxy.allowed(self.socket("127.0.0.1")))
        self.assertFalse(proxy.allowed(self.socket("192.168.1.20")))
        self.assertFalse(proxy.allowed(self.socket("192.168.1.20", "forged")))
        self.assertTrue(proxy.allowed(self.socket("192.168.1.20", auth.issue("admin"))))


if __name__ == "__main__":
    unittest.main()
