import importlib.util
import struct
import unittest
import zlib
from pathlib import Path

DAEMON = Path(__file__).resolve().parents[2] / "client_satellite" / "linux_edge" / "rpa_daemon.py"
spec = importlib.util.spec_from_file_location("rpa_daemon", DAEMON)
daemon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daemon)

W, H = 64, 48


def solid(color=(10, 20, 30), width=W, height=H):
    return daemon.Frame(width, height, bytes(color) * (width * height))


def with_rect(frame, x, y, w, h, color):
    rgb = bytearray(frame.rgb)
    for row in range(y, y + h):
        for col in range(x, x + w):
            rgb[(row * frame.width + col) * 3:(row * frame.width + col) * 3 + 3] = bytes(color)
    return daemon.Frame(frame.width, frame.height, bytes(rgb))


def png_with_filters(frame, channels=3):
    stride = frame.width * 3
    rows = [frame.rgb[y * stride:(y + 1) * stride] for y in range(frame.height)]
    out, previous = bytearray(), bytes(stride)
    for index, row in enumerate(rows):
        kind = index % 5
        filtered = bytearray()
        for i in range(stride):
            a = row[i - 3] if i >= 3 else 0
            b, c = previous[i], (previous[i - 3] if i >= 3 else 0)
            if kind == 0:
                predictor = 0
            elif kind == 1:
                predictor = a
            elif kind == 2:
                predictor = b
            elif kind == 3:
                predictor = (a + b) >> 1
            else:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                predictor = a if pa <= pb and pa <= pc else b if pb <= pc else c
            filtered.append((row[i] - predictor) & 255)
        out += bytes([kind]) + filtered
        previous = row

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", frame.width, frame.height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(out))) + chunk(b"IEND", b""))


class ValidationTest(unittest.TestCase):
    def check(self, instruction):
        return daemon.validate(instruction, W, H)

    def test_valid_instructions(self):
        self.assertEqual(self.check({"id": "1", "action": "click", "x": 3, "y": 4})["x"], 3)
        self.assertEqual(self.check({"action": "drag", "x": 1, "y": 1, "x2": 9, "y2": 9})["y2"], 9)
        self.assertEqual(self.check({"action": "type", "text": "Hello, World! 123"})["text"], "Hello, World! 123")
        self.assertEqual(self.check({"action": "key", "keys": ["ctrl", "s"]})["keys"], ["ctrl", "s"])
        self.assertEqual(self.check({"action": "click", "x": 5, "y": 5, "region": [0, 0, 10, 10], "min_contrast": 3})["min_contrast"], 3.0)
        self.assertEqual(self.check({"action": "capture"})["action"], "capture")

    def test_rejections(self):
        bad = [
            {"action": "format_disk"}, {"action": "click"}, {"action": "click", "x": W, "y": 1}, {"action": "click", "x": -1, "y": 1},
            {"action": "click", "x": 1.5, "y": 1}, {"action": "click", "x": True, "y": 1}, {"action": "drag", "x": 1, "y": 1},
            {"action": "type", "text": ""}, {"action": "type", "text": "caffè"}, {"action": "type", "text": "x" * 501},
            {"action": "type", "text": "line\nbreak"}, {"action": "key", "keys": ["nonexistent"]}, {"action": "key", "keys": []},
            {"action": "key", "keys": ["a", "b", "c", "d", "e"]}, {"action": "scroll", "amount": 0}, {"action": "scroll", "amount": 99},
            {"action": "wait", "seconds": 0}, {"action": "wait", "seconds": 60},
            {"action": "click", "x": 1, "y": 1, "region": [0, 0, W + 1, 5]}, {"action": "click", "x": 1, "y": 1, "region": [0, 0, 0, 5]},
            {"action": "click", "x": 1, "y": 1, "min_contrast": 3}, {"action": "click", "x": 1, "y": 1, "region": [0, 0, 5, 5], "min_contrast": 999},
        ]
        for instruction in bad:
            with self.subTest(instruction=instruction), self.assertRaises(ValueError):
                self.check(instruction)

    def test_unknown_fields_are_dropped(self):
        clean = self.check({"action": "click", "x": 1, "y": 1, "shell": "rm -rf /"})
        self.assertNotIn("shell", clean)


class PngTest(unittest.TestCase):
    def test_encode_decode_round_trip(self):
        frame = with_rect(solid(), 5, 6, 10, 8, (200, 100, 50))
        decoded = daemon.decode_png_pure(frame.to_png())
        self.assertEqual((decoded.width, decoded.height, decoded.rgb), (frame.width, frame.height, frame.rgb))

    def test_all_five_png_filters_decode_correctly(self):
        pattern = bytes((x * 7 + y * 13 + c * 31) % 256 for y in range(H) for x in range(W) for c in range(3))
        frame = daemon.Frame(W, H, pattern)
        self.assertEqual(daemon.decode_png_pure(png_with_filters(frame)).rgb, pattern)

    def test_public_decoder_matches_pure_decoder(self):
        frame = with_rect(solid(), 1, 1, 4, 4, (9, 9, 9))
        self.assertEqual(daemon.decode_png(frame.to_png()).rgb, frame.rgb)

    def test_rejects_garbage_and_unsupported_formats(self):
        with self.assertRaises(ValueError):
            daemon.decode_png(b"not a png")
        interlaced = bytearray(solid().to_png())
        interlaced[28] = 1
        with self.assertRaises(Exception):
            daemon.decode_png_pure(bytes(interlaced))


class PixelAnalysisTest(unittest.TestCase):
    def test_identical_frames_have_no_change(self):
        self.assertEqual(daemon.changed_ratio(solid(), solid()), 0.0)

    def test_change_is_proportional_and_region_aware(self):
        after = with_rect(solid(), 0, 0, 32, 48, (250, 250, 250))
        self.assertAlmostEqual(daemon.changed_ratio(solid(), after), 0.5, delta=0.05)
        self.assertGreater(daemon.changed_ratio(solid(), after, [0, 0, 16, 16]), 0.95)
        self.assertEqual(daemon.changed_ratio(solid(), after, [40, 0, 16, 16]), 0.0)

    def test_small_noise_below_tolerance_is_ignored(self):
        self.assertEqual(daemon.changed_ratio(solid(), solid((12, 22, 32))), 0.0)

    def test_size_change_counts_as_full_change(self):
        self.assertEqual(daemon.changed_ratio(solid(), solid(width=32)), 1.0)

    def test_contrast_distinguishes_flat_areas_from_content(self):
        self.assertEqual(daemon.region_contrast(solid(), [0, 0, 20, 20]), 0.0)
        button = with_rect(solid(), 10, 10, 8, 8, (255, 255, 255))
        self.assertGreater(daemon.region_contrast(button, [8, 8, 12, 12]), 30)


class KeystrokeTest(unittest.TestCase):
    def test_lowercase_letter(self):
        self.assertEqual(daemon.keystrokes("a"), [(30, True), (30, False)])

    def test_uppercase_uses_shift(self):
        self.assertEqual(daemon.keystrokes("A"), [(42, True), (30, True), (30, False), (42, False)])

    def test_symbols_and_space(self):
        self.assertEqual(daemon.keystrokes("!")[1][0], daemon.KEYS["1"])
        self.assertEqual(daemon.keystrokes(" ")[0][0], daemon.KEYS["space"])
        self.assertEqual(daemon.keystrokes("|")[1][0], daemon.KEYS["\\"])

    def test_unknown_characters_fail(self):
        with self.assertRaises(ValueError):
            daemon.keystrokes("é")


class FakeDevice:
    def __init__(self):
        self.events = []

    def move(self, x, y):
        self.events.append(("move", x, y))

    def button(self, name, pressed):
        self.events.append(("button", name, pressed))

    def key(self, code, pressed):
        self.events.append(("key", code, pressed))

    def wheel(self, amount):
        self.events.append(("wheel", amount))


def executor(frames, device=None):
    sequence = iter(frames)
    last = []

    def grab():
        try:
            last[:] = [next(sequence)]
        except StopIteration:
            pass
        return last[0]

    return daemon.Executor(device or FakeDevice(), grab=grab, sleep=lambda _: None), grab


class ExecutorTest(unittest.TestCase):
    def test_click_reports_pixel_change_after_the_screen_settles(self):
        changed = with_rect(solid(), 10, 10, 20, 20, (255, 255, 255))
        ex, _ = executor([changed, changed, changed])
        data = ex.run(daemon.validate({"action": "click", "x": 12, "y": 12, "region": [10, 10, 20, 20]}, W, H), solid())
        self.assertTrue(data["settled"])
        self.assertGreater(data["changed_ratio"], 0.05)
        self.assertGreater(data["region_ratio"], 0.9)
        self.assertTrue(data["acted"])
        self.assertEqual(ex.device.events, [("move", 12, 12), ("button", "left", True), ("button", "left", False)])

    def test_click_without_visible_effect_reports_zero(self):
        ex, _ = executor([solid(), solid(), solid()])
        data = ex.run(daemon.validate({"action": "click", "x": 2, "y": 2}, W, H), solid())
        self.assertEqual(data["changed_ratio"], 0.0)

    def test_flat_anchor_is_not_clicked(self):
        ex, _ = executor([solid()])
        data = ex.run(daemon.validate({"action": "click", "x": 2, "y": 2, "region": [0, 0, 20, 20], "min_contrast": 3}, W, H), solid())
        self.assertFalse(data["acted"])
        self.assertEqual(ex.device.events, [])

    def test_content_anchor_is_clicked(self):
        base = with_rect(solid(), 0, 0, 10, 10, (255, 255, 255))
        ex, _ = executor([base, base])
        data = ex.run(daemon.validate({"action": "click", "x": 2, "y": 2, "region": [0, 0, 20, 20], "min_contrast": 3}, W, H), base)
        self.assertTrue(data["acted"])
        self.assertGreater(data["anchor_contrast"], 3)

    def test_unsettled_screen_is_reported(self):
        flicker = [solid(), with_rect(solid(), 0, 0, 40, 40, (255, 255, 255))]
        frames = [flicker[i % 2] for i in range(40)]
        ex, _ = executor(frames)
        ticks = iter(range(0, 1000))
        original = daemon.time.monotonic
        daemon.time.monotonic = lambda: next(ticks) * 1.0
        try:
            data = ex.run(daemon.validate({"action": "move", "x": 1, "y": 1}, W, H), solid())
        finally:
            daemon.time.monotonic = original
        self.assertFalse(data["settled"])

    def test_drag_press_move_release(self):
        ex, _ = executor([solid(), solid()])
        ex.run(daemon.validate({"action": "drag", "x": 1, "y": 1, "x2": 31, "y2": 21}, W, H), solid())
        kinds = [e[0] + (":" + str(e[2]) if e[0] == "button" else "") for e in ex.device.events]
        self.assertEqual(kinds[0:2], ["move", "button:True"])
        self.assertEqual(kinds[-1], "button:False")
        self.assertEqual(ex.device.events[-2], ("move", 31, 21))

    def test_key_combo_presses_then_releases_in_reverse(self):
        ex, _ = executor([solid(), solid()])
        ex.run(daemon.validate({"action": "key", "keys": ["ctrl", "s"]}, W, H), solid())
        self.assertEqual(ex.device.events, [("key", 29, True), ("key", 31, True), ("key", 31, False), ("key", 29, False)])

    def test_type_scroll_and_double_click(self):
        ex, _ = executor([solid()] * 6)
        ex.run(daemon.validate({"action": "scroll", "amount": -3}, W, H), solid())
        ex.run(daemon.validate({"action": "double_click", "x": 3, "y": 3}, W, H), solid())
        ex.run(daemon.validate({"action": "right_click", "x": 3, "y": 3}, W, H), solid())
        self.assertIn(("wheel", -3), ex.device.events)
        self.assertEqual(sum(1 for e in ex.device.events if e == ("button", "left", True)), 2)
        self.assertIn(("button", "right", True), ex.device.events)

    def test_capture_does_not_touch_the_input_device(self):
        ex, _ = executor([solid()])
        data = ex.run(daemon.validate({"action": "capture"}, W, H), solid())
        self.assertEqual((data["width"], data["height"], ex.device.events), (W, H, []))


class HandleTest(unittest.TestCase):
    def test_capture_returns_a_png_the_server_can_decode(self):
        ex, grab = executor([solid()])
        result = daemon.handle({"id": "abc", "action": "capture"}, ex, grab)
        self.assertTrue(result["ok"])
        self.assertEqual(result["id"], "abc")
        import base64
        self.assertEqual(daemon.decode_png(base64.b64decode(result["frame"])).width, W)

    def test_invalid_instruction_returns_an_error_instead_of_raising(self):
        ex, grab = executor([solid()])
        result = daemon.handle({"id": "x", "action": "click", "x": 9999, "y": 1}, ex, grab)
        self.assertFalse(result["ok"])
        self.assertIn("ValueError", result["error"])
        self.assertEqual(ex.device.events, [])

    def test_capture_backend_failure_is_reported(self):
        def broken():
            raise OSError("no screen")

        result = daemon.handle({"id": "x", "action": "capture"}, daemon.Executor(FakeDevice()), broken)
        self.assertFalse(result["ok"])
        self.assertIn("no screen", result["error"])


if __name__ == "__main__":
    unittest.main()
