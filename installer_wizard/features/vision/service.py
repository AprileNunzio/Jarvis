import asyncio
import logging
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from gallery import FACES, Gallery, slugify
from objects import ObjectDetector
from tracks import Track, facing, iou, reliable_unknown

log = logging.getLogger("jarvis.vision")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

MODELS = Path(os.environ.get("JARVIS_VISION_MODELS", "/opt/jarvis-vision/models"))
DEVICE = os.environ.get("JARVIS_CAMERA", "/dev/video0")
PORT = int(os.environ.get("JARVIS_VISION_PORT", "8091"))
OBJECT_MODEL = MODELS / "object_detection_nanodet_2022nov.onnx"
NEAR_RATIO = 0.16
DETECT_FPS = 4
OBJECT_EVERY = 1.2
FEATURE_EVERY = 3
AUTO_ENROLL = os.environ.get("JARVIS_AUTO_ENROLL", "1") != "0"
AUTO_MIN_SECONDS = 2.5
AUTO_MIN_RATIO = 0.09
AUTO_SAMPLES = 8
MERGE_THRESHOLD = 0.30
ECHO_THRESHOLD = 0.20
UNKNOWN_MIN_RATIO = 0.05
LEARN_UNTIL = 25


class Vision:
    def __init__(self, gallery: Gallery) -> None:
        self.gallery = gallery
        self.status = "starting"
        self.error = ""
        self.raw = None
        self.annotated_jpeg = b""
        self.tracks: list[Track] = []
        self.size = (640, 480)
        self.lock = threading.Lock()
        self.enroll_request = None
        self.frame_id = 0
        self.last_process = 0.0
        self.fast_until = 0.0
        self.detector = cv2.FaceDetectorYN.create(str(MODELS / "face_detection_yunet_2023mar.onnx"), "",
                                                  self.size, 0.85, 0.3, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(str(MODELS / "face_recognition_sface_2021dec.onnx"), "")
        self.objects = ObjectDetector(OBJECT_MODEL) if OBJECT_MODEL.exists() else None
        threading.Thread(target=self._loop, daemon=True).start()
        if self.objects:
            threading.Thread(target=self._object_loop, daemon=True).start()

    def _open(self):
        cap = cv2.VideoCapture(DEVICE, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _loop(self) -> None:
        while True:
            cap = self._open()
            if not cap.isOpened():
                self.status, self.error = "no_camera", f"Webcam non disponibile ({DEVICE})"
                time.sleep(10)
                continue
            self.status, self.error = "ok", ""
            log.info("Webcam aperta: %s", DEVICE)
            failures = 0
            while failures < 30:
                start = time.time()
                ok, frame = cap.read()
                if not ok or frame is None:
                    failures += 1
                    time.sleep(0.2)
                    continue
                failures = 0
                with self.lock:
                    self.raw = frame.copy()
                    self.frame_id += 1
                if start - self.last_process >= 1 / DETECT_FPS:
                    self.last_process = start
                    try:
                        self._process(frame)
                    except cv2.error as exc:
                        log.warning("Errore di elaborazione: %s", exc)
                if start > self.fast_until:
                    time.sleep(max(0.0, 1 / DETECT_FPS - (time.time() - start)))
            cap.release()
            self.status, self.error = "no_camera", "Flusso video interrotto: riconnessione"
            time.sleep(3)

    def _object_loop(self) -> None:
        while True:
            time.sleep(OBJECT_EVERY)
            with self.lock:
                frame = None if self.raw is None else self.raw.copy()
            if frame is None:
                continue
            try:
                self.objects.update(frame, [t.box for t in self.tracks])
            except cv2.error as exc:
                log.warning("Riconoscimento oggetti non riuscito: %s", exc)
                time.sleep(10)

    def _process(self, frame) -> None:
        h, w = frame.shape[:2]
        if (w, h) != self.size:
            self.size = (w, h)
            self.detector.setInputSize(self.size)
        _, faces = self.detector.detect(frame)
        faces = faces if faces is not None else []
        now = time.time()

        unmatched = list(self.tracks)
        current, detections = [], []
        for face in faces:
            box = tuple(int(v) for v in face[:4])
            best = max(unmatched, key=lambda t: iou(t.box, box), default=None)
            track = best if best is not None and iou(best.box, box) > 0.25 else Track(box)
            if track in unmatched:
                unmatched.remove(track)
            track.box, track.last_seen = box, now
            track.facing = facing(face)
            track.frames += 1
            need = (len(track.votes) < 3 or track.frames % FEATURE_EVERY == 0
                    or self.enroll_request is not None)
            if need:
                feature = self.recognizer.feature(self.recognizer.alignCrop(frame, face)).flatten()
                track.feature = feature
                track.votes.append(self.gallery.match(feature))
                detections.append((box, feature, face))
            current.append(track)
        self.tracks = current + [t for t in unmatched if now - t.last_seen < 1.5]
        self._mark_echoes()
        for box, feature, _ in detections:
            track = next((t for t in current if t.box == box), None)
            if track:
                self._learn(track, frame, feature)

        if self.enroll_request is not None and detections:
            largest = max(detections, key=lambda d: d[0][2] * d[0][3])
            req = self.enroll_request
            req["samples"].append(largest[1])
            if req.get("photo") is None:
                req["photo"] = self._crop(frame, largest[0])

        self._annotate(frame)

    def _mark_echoes(self) -> None:
        known = {t.identity()[0] for t in self.tracks if t.identity()[0]}
        for t in self.tracks:
            t.echo_of = None
            if t.identity()[0] or t.feature is None or not known:
                continue
            slug, score = self.gallery.closest(t.feature)
            if slug in known and score >= ECHO_THRESHOLD:
                t.echo_of = slug

    def _crop(self, frame, box):
        x, y, bw, bh = box
        pad = int(bw * 0.35)
        return frame[max(0, y - pad):y + bh + pad, max(0, x - pad):x + bw + pad].copy()

    def _learn(self, track: Track, frame, feature) -> None:
        if not AUTO_ENROLL or self.enroll_request is not None or track.echo_of:
            return
        now = time.time()
        slug, name, score = track.identity()
        ratio = track.box[2] / (self.size[0] or 640)
        if slug:
            person = self.gallery.people.get(slug, {})
            if person.get("samples", 40) < LEARN_UNTIL and score > 0.5 and now - track.last_learn > 1.5:
                track.last_learn = now
                self.gallery.add_samples(slug, [feature])
            return
        if ratio < AUTO_MIN_RATIO or any(t.identity()[0] for t in self.tracks):
            return
        track.samples.append(feature)
        if now - track.first_seen < AUTO_MIN_SECONDS or len(track.samples) < AUTO_SAMPLES:
            return
        mean = np.mean([s / np.linalg.norm(s) for s in track.samples], axis=0)
        near_slug, near_score = self.gallery.closest(mean)
        if near_slug and near_score >= MERGE_THRESHOLD:
            self.gallery.add_samples(near_slug, track.samples)
            log.info("Campioni aggiunti a %s (somiglianza %.2f)", near_slug, near_score)
        else:
            guest = self.gallery.next_guest_name()
            person = self.gallery.save(guest, track.samples, self._crop(frame, track.box), auto=True,
                                       slug=f"ospite-{int(now)}")
            log.info("Nuova persona registrata automaticamente: %s", person["name"])
        track.samples = []
        track.votes.clear()

    def _annotate(self, frame) -> None:
        for t in self.tracks:
            x, y, bw, bh = t.box
            slug, name, score = t.identity()
            color = (255, 224, 41) if slug else (120, 120, 120) if t.echo_of else (71, 181, 255)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 2)
            label = f"{name} {score:.2f}" if slug else "riflesso" if t.echo_of else name
            cv2.putText(frame, label, (x, max(18, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        for o in (self.objects.objects if self.objects else []):
            if o["scenery"]:
                continue
            x, y, bw, bh = o["box"]
            color = (168, 255, 61) if o["held"] else (255, 120, 180)
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 1)
            cv2.putText(frame, o["label"], (x, y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            with self.lock:
                self.annotated_jpeg = jpg.tobytes()

    def _visible(self, t: Track, now: float) -> bool:
        if t.identity()[0]:
            return True
        return not t.echo_of and reliable_unknown(t, now) and t.box[2] / (self.size[0] or 640) >= UNKNOWN_MIN_RATIO

    def presence(self) -> dict:
        w = self.size[0] or 640
        now = time.time()
        people = []
        for t in self.tracks:
            if not self._visible(t, now):
                continue
            slug, name, score = t.identity()
            bx, by, bw, bh = t.box
            ratio = bw / w
            h = self.size[1] or 480
            person = self.gallery.people.get(slug, {}) if slug else {}
            people.append({"track": t.id, "slug": slug, "name": name, "known": slug is not None,
                           "auto": bool(person.get("auto")), "facing": t.facing,
                           "confidence": round(score, 3), "proximity": round(ratio, 3),
                           "near": ratio >= NEAR_RATIO, "since": t.first_seen,
                           "gaze": {"x": round((bx + bw / 2) / (w or 640), 3),
                                    "y": round((by + bh / 2) / h, 3)}})
        people.sort(key=lambda p: -p["proximity"])
        return {"status": self.status, "error": self.error, "people": people, "objects": self.visible_objects(),
                "time": now}

    def visible_objects(self) -> list:
        if not self.objects or time.time() - self.objects.updated > 10:
            return []
        return [o for o in self.objects.objects if not o["scenery"]]

    def hands_jpeg(self, width: int = 320) -> tuple[int, bytes]:
        self.fast_until = time.time() + 3
        with self.lock:
            frame, fid = (None, 0) if self.raw is None else (self.raw.copy(), self.frame_id)
        if frame is None:
            return 0, b""
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (width, int(h * width / w)), interpolation=cv2.INTER_AREA)
        ok, jpg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return fid, jpg.tobytes() if ok else b""

    def live_jpeg(self, quality: int = 80) -> tuple[int, bytes]:
        self.fast_until = time.time() + 3
        with self.lock:
            frame, fid = (None, 0) if self.raw is None else (self.raw.copy(), self.frame_id)
        if frame is None:
            return 0, b""
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return fid, jpg.tobytes() if ok else b""

    def raw_jpeg(self, quality: int = 88) -> bytes:
        with self.lock:
            frame = None if self.raw is None else self.raw.copy()
        if frame is None:
            return b""
        ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return jpg.tobytes() if ok else b""

    def enroll(self, name: str, seconds: float = 4.0) -> dict:
        self.enroll_request = {"samples": [], "photo": None}
        deadline = time.time() + seconds
        while time.time() < deadline:
            time.sleep(0.1)
        req, self.enroll_request = self.enroll_request, None
        if len(req["samples"]) < 5 or req["photo"] is None:
            raise ValueError("Volto non rilevato con sufficiente chiarezza: avvicinati e guarda la webcam")
        return self.gallery.save(name, req["samples"], req["photo"])


gallery = Gallery()
vision = Vision(gallery)
app = FastAPI(title="Jarvis Vision", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health():
    return {"status": vision.status, "error": vision.error, "people_enrolled": len(gallery.people),
            "objects": vision.objects is not None}


@app.get("/presence")
async def presence():
    return JSONResponse(vision.presence())


@app.get("/objects")
async def objects():
    return {"objects": vision.visible_objects()}


@app.get("/snapshot.jpg")
async def snapshot():
    with vision.lock:
        data = vision.annotated_jpeg
    if not data:
        raise HTTPException(503, "Nessun fotogramma")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/frame.jpg")
async def frame():
    data = vision.raw_jpeg()
    if not data:
        raise HTTPException(503, "Nessun fotogramma")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/stream.mjpg")
async def stream(request: Request):
    async def frames():
        while not await request.is_disconnected():
            with vision.lock:
                data = vision.annotated_jpeg
            if data:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            await asyncio.sleep(1 / DETECT_FPS)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/live.mjpg")
async def live(request: Request):
    async def frames():
        last = -1
        while not await request.is_disconnected():
            fid, data = vision.live_jpeg()
            if data and fid != last:
                last = fid
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            await asyncio.sleep(1 / 20)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/hands.mjpg")
async def hands(request: Request):
    async def frames():
        last = -1
        while not await request.is_disconnected():
            fid, data = vision.hands_jpeg()
            if data and fid != last:
                last = fid
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            await asyncio.sleep(1 / 24)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/people")
async def people():
    return {"people": gallery.listing()}


@app.get("/people/{slug}/photo.jpg")
async def photo(slug: str):
    path = FACES / slugify(slug) / "photo.jpg"
    if not path.exists():
        raise HTTPException(404, "Foto non trovata")
    return Response(path.read_bytes(), media_type="image/jpeg")


@app.post("/people")
async def enroll(request: Request):
    name = str((await request.json()).get("name", "")).strip()
    if not name or len(name) > 40:
        raise HTTPException(400, "Nome non valido")
    if vision.status != "ok":
        raise HTTPException(503, vision.error or "Webcam non disponibile")
    try:
        person = await asyncio.to_thread(vision.enroll, name)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    log.info("Registrato: %s (%d campioni)", person["name"], person["samples"])
    return person


@app.patch("/people/{slug}")
async def rename(slug: str, request: Request):
    name = str((await request.json()).get("name", "")).strip()
    if not name or len(name) > 40:
        raise HTTPException(400, "Nome non valido")
    person = gallery.rename(slugify(slug), name)
    if not person:
        raise HTTPException(404, "Persona non trovata")
    log.info("Rinominato %s → %s", slug, name)
    return person


@app.delete("/people/{slug}")
async def forget(slug: str):
    if not gallery.delete(slugify(slug)):
        raise HTTPException(404, "Persona non trovata")
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
