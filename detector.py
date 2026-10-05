"""Local open-source object detection (Ultralytics YOLO) + evidence-image drawing."""
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent

# Default: YOLOv8s trained on COCO. Set FINDIT_MODEL=yolov8s-worldv2.pt for open-vocabulary mode.
MODEL_NAME = os.environ.get("FINDIT_MODEL", "yolov8s.pt")
CONF_THRESHOLD = float(os.environ.get("FINDIT_CONF", "0.25"))
IMG_SIZE = int(os.environ.get("FINDIT_IMGSZ", "800"))
IS_WORLD = "world" in MODEL_NAME.lower()

COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
]

WORLD_VOCAB = [
    "laptop", "cell phone", "calculator", "keyboard", "mouse", "bottle", "backpack", "book",
    "notebook", "cup", "glasses", "keys", "wallet", "charger", "earphones", "USB drive",
]

SUPPORTED = [c.lower() for c in (WORLD_VOCAB if IS_WORLD else COCO_CLASSES)]

_RAW_ALIASES = {
    "phone": "cell phone", "mobile": "cell phone", "smartphone": "cell phone",
    "cellphone": "cell phone", "iphone": "cell phone",
    "computer": "laptop", "macbook": "laptop",
    "water bottle": "bottle", "bag": "backpack", "rucksack": "backpack",
    "schoolbag": "backpack", "mug": "cup",
    "specs": "glasses", "spectacles": "glasses", "eyeglasses": "glasses",
    "sunglasses": "glasses", "key": "keys", "keychain": "keys",
    "usb": "usb drive", "pendrive": "usb drive", "pen drive": "usb drive",
    "flash drive": "usb drive", "thumb drive": "usb drive",
    "headphones": "earphones", "earbuds": "earphones", "airpods": "earphones",
    "computer mouse": "mouse", "tv remote": "remote", "textbook": "book",
}
if not IS_WORLD:
    _RAW_ALIASES["notebook"] = "book"  # COCO has no notebook class

# Only keep aliases that point at a class the active model really supports.
ALIASES = {a: c for a, c in _RAW_ALIASES.items() if c in SUPPORTED}

_DISPLAY = {"cell phone": "Phone", "usb drive": "USB drive", "tv": "TV"}


def display_name(name):
    name = str(name).lower()
    return _DISPLAY.get(name, name[:1].upper() + name[1:])


class ModelUnavailable(Exception):
    pass


class DetectionError(Exception):
    pass


_model = None
_device = "cpu"


def _pick_device():
    try:
        import torch
        return 0 if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def get_model():
    """Load the model once. Raises ModelUnavailable with a friendly message."""
    global _model, _device
    if _model is not None:
        return _model
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise ModelUnavailable(
            "The detection library is not installed. Run: pip install -r requirements.txt"
        ) from exc

    local = BASE_DIR / "models" / MODEL_NAME
    weights = str(local) if local.exists() else MODEL_NAME
    try:
        if IS_WORLD:
            from ultralytics import YOLOWorld
            model = YOLOWorld(weights)
            model.set_classes(WORLD_VOCAB)
        else:
            model = YOLO(weights)
    except Exception as exc:
        raise ModelUnavailable(
            f"Could not load the detection model '{MODEL_NAME}'. It is downloaded on first run, "
            f"so connect to the internet once, or place the file in the 'models' folder. "
            f"({type(exc).__name__}: {exc})"
        ) from exc
    _device = _pick_device()
    _model = model
    return _model


def model_info():
    get_model()
    gpu = None
    try:
        import torch
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return {
        "model": MODEL_NAME,
        "mode": "open-vocabulary (YOLO-World)" if IS_WORLD else "COCO pretrained",
        "device": f"cuda ({gpu})" if gpu else "cpu",
        "confidence_threshold": CONF_THRESHOLD,
        "supported_classes": SUPPORTED,
    }


def detect(image_path):
    """Run real object detection. Returns list of dicts sorted by confidence."""
    model = get_model()
    try:
        results = model.predict(
            source=str(image_path), conf=CONF_THRESHOLD, imgsz=IMG_SIZE,
            device=_device, verbose=False,
        )
    except Exception as exc:
        raise DetectionError(
            "The detector failed on this image. Try another photo."
        ) from exc

    r = results[0]
    found = []
    for box in r.boxes:
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        found.append({
            "object_name": str(r.names[int(box.cls[0])]).lower(),
            "confidence": float(box.conf[0]),
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        })
    found.sort(key=lambda d: -d["confidence"])
    return found


_COLORS = ["#5b5bf0", "#8b5cf6", "#3b82f6", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444"]


def _font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(image_path, detections, out_path):
    """Draw labelled bounding boxes on a copy of the image and save it as JPEG."""
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    big = max(img.size)
    line = max(3, big // 280)
    font = _font(max(14, big // 50))
    names = {}
    for d in detections:
        color = _COLORS[names.setdefault(d["object_name"], len(names)) % len(_COLORS)]
        x1, y1, x2, y2 = d["x1"], d["y1"], d["x2"], d["y2"]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=line)
        label = f"{display_name(d['object_name'])} {d['confidence'] * 100:.0f}%"
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        tw, th = right - left, bottom - top
        ty = max(0, y1 - th - 10)
        draw.rectangle([x1, ty, x1 + tw + 12, ty + th + 10], fill=color)
        draw.text((x1 + 6, ty + 4), label, fill="white", font=font)
    img.save(out_path, "JPEG", quality=90)


if __name__ == "__main__":
    # Self-test:  python detector.py path\to\photo.jpg
    if len(sys.argv) < 2:
        print("Usage: python detector.py <image>")
        sys.exit(1)
    try:
        info = model_info()
        print(f"Model: {info['model']} | Device: {info['device']}")
        dets = detect(sys.argv[1])
    except (ModelUnavailable, DetectionError) as err:
        print("ERROR:", err)
        sys.exit(2)
    print(f"{len(dets)} object(s) detected")
    for d in dets:
        print(f"  {d['object_name']:<14} {d['confidence']:.2f}  "
              f"[{d['x1']:.0f}, {d['y1']:.0f}, {d['x2']:.0f}, {d['y2']:.0f}]")
    out = BASE_DIR / "processed" / "selftest.jpg"
    out.parent.mkdir(exist_ok=True)
    annotate(sys.argv[1], dets, out)
    print("Annotated image saved to", out)
