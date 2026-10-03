import socket
import threading
import unittest

from sandbox_broker.docker_cmd import build_run_argv
from sandbox_broker.egress import EgressProxy, host_matches, public_address, split_target
from server.features.sandbox.domain.errors import SpecError
from server.features.sandbox.domain.report import ExecutionReport
from server.features.sandbox.domain.spec import ExecutionSpec, Language, NetworkPolicy, valid_egress_host

PUBLIC_IP = "93.184.216.34"


def resolver_for(table):
    def resolve(host, port, type=0):
        if host not in table:
            raise socket.gaierror("unknown host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in table[host]]

    return resolve


class UpstreamServer:
    def __init__(self, reply=b""):
        self.received = b""
        self.reply = reply
        self._server = socket.socket()
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(4)
        self.port = self._server.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while True:
            try:
                connection, _ = self._server.accept()
            except OSError:
                return
            with connection:
                connection.settimeout(2)
                try:
                    while True:
                        data = connection.recv(65536)
                        if not data:
                            break
                        self.received += data
                        connection.sendall(self.reply or data)
                        if self.reply:
                            break
                except OSError:
                    pass

    def close(self):
        self._server.close()


def proxy_for(upstream, allowed, table=None, **kwargs):
    table = table or {"api.example.com": [PUBLIC_IP], "files.example.com": [PUBLIC_IP]}

    def connect(address, timeout):
        return socket.create_connection(("127.0.0.1", upstream.port), timeout)

    return EgressProxy("127.0.0.1", allowed, kwargs.pop("lifetime", 10), resolver=resolver_for(table), connect=connect, **kwargs)


def talk(proxy, payload, read=65536, shutdown=False):
    with socket.create_connection(("127.0.0.1", proxy.port), timeout=3) as client:
        client.sendall(payload)
        if shutdown:
            client.shutdown(socket.SHUT_WR)
        client.settimeout(3)
        out = b""
        try:
            while True:
                chunk = client.recv(read)
                if not chunk:
                    break
                out += chunk
        except socket.timeout:
            pass
        return out


class HostMatchingTest(unittest.TestCase):
    def test_exact_and_wildcard(self):
        self.assertTrue(host_matches("api.example.com", ["api.example.com"]))
        self.assertTrue(host_matches("API.Example.com.", ["api.example.com"]))
        self.assertTrue(host_matches("a.b.example.com", ["*.example.com"]))
        self.assertFalse(host_matches("example.com", ["*.example.com"]))
        self.assertFalse(host_matches("evilexample.com", ["*.example.com"]))
        self.assertFalse(host_matches("api.example.com.evil.net", ["api.example.com"]))
        self.assertFalse(host_matches("anything.org", []))

    def test_spec_host_validation(self):
        for good in ("api.example.com", "*.github.com", "a-b.co.uk"):
            self.assertTrue(valid_egress_host(good), good)
        for bad in ("localhost", "127.0.0.1", "*.com", "a b.com", "http://x.com", "x.com/path", "*", "a..com", "-a.com", ""):
            self.assertFalse(valid_egress_host(bad), bad)


class AddressSafetyTest(unittest.TestCase):
    def test_only_global_addresses_pass(self):
        ok = public_address("h", resolver_for({"h": [PUBLIC_IP]}))
        self.assertEqual(ok, PUBLIC_IP)
        for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.9", "172.16.0.1", "169.254.169.254", "100.64.0.1", "0.0.0.0", "::1", "fe80::1"):
            with self.subTest(ip=ip):
                self.assertIsNone(public_address("h", resolver_for({"h": [ip]})))

    def test_one_private_answer_poisons_the_whole_set(self):
        self.assertIsNone(public_address("h", resolver_for({"h": [PUBLIC_IP, "10.0.0.1"]})))

    def test_unresolvable_host(self):
        self.assertIsNone(public_address("nope", resolver_for({})))


class TargetParsingTest(unittest.TestCase):
    def test_connect(self):
        self.assertEqual(split_target(b"CONNECT api.example.com:443 HTTP/1.1\r\nHost: x\r\n\r\n")[:3], ("CONNECT", "api.example.com", 443))

    def test_absolute_http_url_becomes_origin_form_without_proxy_headers(self):
        method, host, port, forwarded = split_target(
            b"GET http://api.example.com/v1/x?y=1 HTTP/1.1\r\nHost: api.example.com\r\nProxy-Connection: keep-alive\r\nAccept: */*\r\n\r\n")
        self.assertEqual((method, host, port), ("GET", "api.example.com", 80))
        self.assertTrue(forwarded.startswith(b"GET /v1/x?y=1 HTTP/1.1\r\n"))
        self.assertNotIn(b"Proxy-", forwarded)
        self.assertIn(b"Connection: close", forwarded)
        self.assertIn(b"Accept: */*", forwarded)

    def test_rejects_malformed_and_non_http(self):
        for head in (b"garbage\r\n\r\n", b"GET /relative HTTP/1.1\r\n\r\n", b"GET ftp://x.com/ HTTP/1.1\r\n\r\n", b"A B\r\n\r\n"):
            with self.subTest(head=head), self.assertRaises(ValueError):
                split_target(head)


class ProxyBehaviourTest(unittest.TestCase):
    def test_allowed_connect_tunnels_bytes_both_ways(self):
        upstream = UpstreamServer()
        self.addCleanup(upstream.close)
        with proxy_for(upstream, ["api.example.com"]) as proxy:
            with socket.create_connection(("127.0.0.1", proxy.port), timeout=3) as client:
                client.sendall(b"CONNECT api.example.com:443 HTTP/1.1\r\nHost: api.example.com:443\r\n\r\n")
                self.assertIn(b"200", client.recv(4096))
                client.sendall(b"ping")
                self.assertEqual(client.recv(4096), b"ping")
        self.assertEqual(proxy.denied, [])

    def test_host_outside_the_allowlist_is_refused_and_recorded(self):
        upstream = UpstreamServer()
        self.addCleanup(upstream.close)
        with proxy_for(upstream, ["api.example.com"]) as proxy:
            answer = talk(proxy, b"CONNECT files.example.com:443 HTTP/1.1\r\n\r\n")
        self.assertIn(b"403", answer)
        self.assertEqual(proxy.denied, ["files.example.com"])
        self.assertEqual(upstream.received, b"")

    def test_ports_other_than_web_ports_are_refused(self):
        upstream = UpstreamServer()
        self.addCleanup(upstream.close)
        with proxy_for(upstream, ["api.example.com"]) as proxy:
            for port in (22, 25, 3306, 8443):
                with self.subTest(port=port):
                    self.assertIn(b"403", talk(proxy, f"CONNECT api.example.com:{port} HTTP/1.1\r\n\r\n".encode()))
        self.assertEqual(upstream.received, b"")

    def test_allowlisted_name_that_resolves_to_a_private_address_is_refused(self):
        upstream = UpstreamServer()
        self.addCleanup(upstream.close)
        table = {"api.example.com": ["169.254.169.254"]}
        with proxy_for(upstream, ["api.example.com"], table) as proxy:
            answer = talk(proxy, b"CONNECT api.example.com:443 HTTP/1.1\r\n\r\n")
        self.assertIn(b"403", answer)
        self.assertEqual(upstream.received, b"")

    def test_ip_literals_never_match_a_name_allowlist(self):
        upstream = UpstreamServer()
        self.addCleanup(upstream.close)
        with proxy_for(upstream, ["api.example.com"]) as proxy:
            self.assertIn(b"403", talk(proxy, b"CONNECT 93.184.216.34:443 HTTP/1.1\r\n\r\n"))
            self.assertIn(b"403", talk(proxy, b"CONNECT 127.0.0.1:443 HTTP/1.1\r\n\r\n"))

    def test_plain_http_is_forwarded_in_origin_form_with_body(self):
        upstream = UpstreamServer(reply=b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
        self.addCleanup(upstream.close)
        request = (b"POST http://api.example.com/submit HTTP/1.1\r\nHost: api.example.com\r\nContent-Length: 5\r\n"
                   b"Proxy-Authorization: x\r\n\r\nhello")
        with proxy_for(upstream, ["api.example.com"]) as proxy:
            answer = talk(proxy, request)
        self.assertTrue(answer.endswith(b"ok"))
        self.assertTrue(upstream.received.startswith(b"POST /submit HTTP/1.1\r\n"))
        self.assertTrue(upstream.received.endswith(b"hello"))
        self.assertNotIn(b"Proxy-", upstream.received)

    def test_malformed_request_gets_400(self):
        upstream = UpstreamServer()
        self.addCleanup(upstream.close)
        with proxy_for(upstream, ["api.example.com"]) as proxy:
            self.assertIn(b"400", talk(proxy, b"not http at all\r\n\r\n"))
            self.assertIn(b"400", talk(proxy, b"GET /relative HTTP/1.1\r\n\r\n"))

    def test_upstream_failure_is_a_bad_gateway(self):
        upstream = UpstreamServer()
        self.addCleanup(upstream.close)

        def refuse(address, timeout):
            raise ConnectionRefusedError

        with EgressProxy("127.0.0.1", ["api.example.com"], 5, resolver=resolver_for({"api.example.com": [PUBLIC_IP]}), connect=refuse) as proxy:
            self.assertIn(b"502", talk(proxy, b"CONNECT api.example.com:443 HTTP/1.1\r\n\r\n"))

    def test_transfer_cap_stops_a_runaway_download(self):
        upstream = UpstreamServer()
        self.addCleanup(upstream.close)
        with proxy_for(upstream, ["api.example.com"], max_bytes=1000) as proxy:
            with socket.create_connection(("127.0.0.1", proxy.port), timeout=3) as client:
                client.sendall(b"CONNECT api.example.com:443 HTTP/1.1\r\n\r\n")
                client.recv(4096)
                client.settimeout(3)
                received = 0
                try:
                    for _ in range(40):
                        client.sendall(b"x" * 500)
                        data = client.recv(4096)
                        if not data:
                            break
                        received += len(data)
                except OSError:
                    pass
        self.assertLess(received, 5000)

    def test_free_port_is_found_inside_the_configured_range_and_exhaustion_fails(self):
        holder = socket.socket()
        holder.bind(("127.0.0.1", 0))
        taken = holder.getsockname()[1]
        holder.listen(1)
        self.addCleanup(holder.close)
        with self.assertRaises(OSError):
            EgressProxy("127.0.0.1", ["a.example.com"], 5, port_range=(taken, taken))


class SpecAndCommandTest(unittest.TestCase):
    def spec(self, **overrides):
        values = {"language": Language.PYTHON, "source": "print(1)", "network": NetworkPolicy.ALLOWLIST, "egress_hosts": ("api.example.com",)}
        values.update(overrides)
        return ExecutionSpec(**values)

    def test_allowlist_requires_valid_hosts_and_none_forbids_them(self):
        self.spec().validate()
        for overrides in ({"egress_hosts": ()}, {"egress_hosts": ("127.0.0.1",)}, {"egress_hosts": ("a.com",) * 9},
                          {"network": NetworkPolicy.NONE}):
            with self.subTest(overrides=overrides), self.assertRaises(SpecError):
                self.spec(**overrides).validate()

    def test_wire_round_trip_keeps_the_allowlist(self):
        spec = self.spec(egress_hosts=("api.example.com", "*.github.com"))
        self.assertEqual(ExecutionSpec.from_wire(spec.to_wire()), spec)

    def test_report_carries_denied_hosts(self):
        report = ExecutionReport(0, "", "", False, False, "c", 1, egress_denied=("evil.com",))
        self.assertEqual(ExecutionReport.from_wire(report.to_wire()).egress_denied, ("evil.com",))

    def test_docker_command_uses_the_internal_network_and_proxy_only_for_allowlists(self):
        argv = build_run_argv("docker", "c", "img", self.spec(), "/in", "/out", 65534, None, "jarvis-sbx", "http://172.29.240.1:38000")
        joined = " ".join(argv)
        self.assertIn("--network jarvis-sbx", joined)
        self.assertIn("HTTPS_PROXY=http://172.29.240.1:38000", joined)
        none = build_run_argv("docker", "c", "img", self.spec(network=NetworkPolicy.NONE, egress_hosts=()), "/in", "/out", 65534,
                              None, "jarvis-sbx", "http://172.29.240.1:38000")
        self.assertIn("--network none", " ".join(none))
        self.assertNotIn("PROXY", " ".join(none))
        fallback = build_run_argv("docker", "c", "img", self.spec(), "/in", "/out", 65534)
        self.assertIn("--network none", " ".join(fallback))


if __name__ == "__main__":
    unittest.main()
