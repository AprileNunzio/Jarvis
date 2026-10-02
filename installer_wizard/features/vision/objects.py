import math
import time
from pathlib import Path

import cv2
import numpy as np

INPUT = 416
STRIDES = (8, 16, 32)
REG_MAX = 7
SCORE = 0.42
NMS_IOU = 0.6
MEAN = np.array([103.53, 116.28, 123.675], dtype=np.float32).reshape(1, 1, 3)
STD = np.array([57.375, 57.12, 58.395], dtype=np.float32).reshape(1, 1, 3)

LABELS_IT = (
    "persona", "bicicletta", "automobile", "moto", "aereo", "autobus", "treno", "camion", "barca", "semaforo",
    "idrante", "segnale di stop", "parchimetro", "panchina", "uccello", "gatto", "cane", "cavallo", "pecora", "mucca",
    "elefante", "orso", "zebra", "giraffa", "zaino", "ombrello", "borsa", "cravatta", "valigia", "frisbee",
    "sci", "snowboard", "palla", "aquilone", "mazza da baseball", "guantone", "skateboard", "tavola da surf",
    "racchetta da tennis", "bottiglia", "bicchiere da vino", "tazza", "forchetta", "coltello", "cucchiaio", "ciotola",
    "banana", "mela", "panino", "arancia", "broccolo", "carota", "hot dog", "pizza", "ciambella", "torta",
    "sedia", "divano", "pianta", "letto", "tavolo", "water", "televisore", "portatile", "mouse", "telecomando",
    "tastiera", "cellulare", "microonde", "forno", "tostapane", "lavello", "frigorifero", "libro", "orologio", "vaso",
    "forbici", "orsacchiotto", "asciugacapelli", "spazzolino",
)
SCENERY = {"persona", "sedia", "divano", "letto", "tavolo", "water", "televisore", "lavello", "frigorifero", "forno",
           "pianta", "microonde", "automobile", "autobus", "treno", "camion", "barca", "aereo", "panchina", "idrante",
           "semaforo", "segnale di stop", "parchimetro"}


def _anchors() -> list:
    grids = []
    for stride in STRIDES:
        size = int(math.ceil(INPUT / stride))
        xv, yv = np.meshgrid(np.arange(size) * stride, np.arange(size) * stride)
        grids.append(np.column_stack((xv.flatten() + 0.5 * (stride - 1), yv.flatten() + 0.5 * (stride - 1))))
    return grids


class ObjectDetector:

    def __init__(self, model: Path) -> None:
        self.net = cv2.dnn.readNet(str(model))
        self.anchors = _anchors()
        self.project = np.arange(REG_MAX + 1)
        self.objects: list = []
        self.updated = 0.0

    def _letterbox(self, frame) -> tuple[np.ndarray, float, int, int]:
        h, w = frame.shape[:2]
        scale = INPUT / max(h, w)
        nh, nw = int(round(h * scale)), int(round(w * scale))
        canvas = np.zeros((INPUT, INPUT, 3), dtype=np.uint8)
        top, left = (INPUT - nh) // 2, (INPUT - nw) // 2
        canvas[top:top + nh, left:left + nw] = cv2.resize(frame, (nw, nh))
        return canvas, scale, left, top

    def _outputs(self, blob) -> list:
        self.net.setInput(blob)
        outs = [o.squeeze(0) if o.ndim == 3 else o for o in self.net.forward(self.net.getUnconnectedOutLayersNames())]
        classes = sorted((o for o in outs if o.shape[1] == len(LABELS_IT)), key=lambda o: -o.shape[0])
        boxes = sorted((o for o in outs if o.shape[1] == 4 * (REG_MAX + 1)), key=lambda o: -o.shape[0])
        return list(zip(classes, boxes))

    def detect(self, frame) -> list:
        canvas, scale, left, top = self._letterbox(frame)
        blob = cv2.dnn.blobFromImage((canvas.astype(np.float32) - MEAN) / STD)
        all_boxes, all_scores = [], []
        for stride, anchors, (cls, reg) in zip(STRIDES, self.anchors, self._outputs(blob)):
            e = np.exp(reg.reshape(-1, REG_MAX + 1) - reg.reshape(-1, REG_MAX + 1).max(axis=1, keepdims=True))
            dist = ((e / e.sum(axis=1, keepdims=True)) @ self.project).reshape(-1, 4) * stride
            x1, y1 = anchors[:, 0] - dist[:, 0], anchors[:, 1] - dist[:, 1]
            x2, y2 = anchors[:, 0] + dist[:, 2], anchors[:, 1] + dist[:, 3]
            all_boxes.append(np.column_stack([x1, y1, x2, y2]))
            all_scores.append(cls)
        boxes, scores = np.concatenate(all_boxes), np.concatenate(all_scores)
        ids, conf = scores.argmax(axis=1), scores.max(axis=1)
        keep = conf >= SCORE
        boxes, ids, conf = boxes[keep], ids[keep], conf[keep]
        if not len(boxes):
            return []
        xywh = np.column_stack([boxes[:, :2], boxes[:, 2:] - boxes[:, :2]])
        found = []
        for i in np.array(cv2.dnn.NMSBoxes(xywh.tolist(), conf.tolist(), SCORE, NMS_IOU)).flatten():
            x1, y1, x2, y2 = boxes[i]
            x, y = (x1 - left) / scale, (y1 - top) / scale
            found.append({"label": LABELS_IT[int(ids[i])], "score": round(float(conf[i]), 2),
                          "box": [int(max(0, x)), int(max(0, y)), int((x2 - x1) / scale), int((y2 - y1) / scale)]})
        return found

    def update(self, frame, faces: list) -> list:
        h, w = frame.shape[:2]
        found = self.detect(frame)
        for o in found:
            o["held"] = held(o, faces, w, h)
            o["scenery"] = o["label"] in SCENERY
        self.objects, self.updated = found, time.time()
        return found


def held(obj: dict, faces: list, width: int, height: int) -> bool:
    if obj["label"] in SCENERY:
        return False
    x, y, bw, bh = obj["box"]
    if bw * bh > 0.45 * width * height:
        return False
    cx, cy = x + bw / 2, y + bh / 2
    for fx, fy, fw, fh in faces:
        reach_x = fw * 3.2
        if abs(cx - (fx + fw / 2)) < reach_x and fy - fh < cy < fy + fh * 6:
            return True
    return False
