"""FindIt AI: Flask app. Run with:  python app.py"""
import os
import uuid
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.exceptions import HTTPException

import database as db
import detector
from search import extract_object

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_UPLOAD_MB = 12
MAX_SIDE = 1600

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
app.config["SECRET_KEY"] = os.environ.get("FINDIT_SECRET", "findit-local-dev-key")

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)
db.init_db()


# ---------- template helpers ----------
@app.template_filter("pretty_time")
def pretty_time(value):
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%B')} {dt.day}, {dt.year} — {hour}:{dt.minute:02d} {ampm}"


app.add_template_filter(detector.display_name, "label")


# ---------- image handling ----------
class ImageProblem(Exception):
    pass


def save_upload(file):
    """Validate, normalise (EXIF rotate, RGB, max 1600px) and store as JPEG."""
    if not file or not file.filename:
        raise ImageProblem("Please choose an image to scan.")
    if Path(file.filename).suffix.lower() not in ALLOWED_EXT:
        raise ImageProblem("Unsupported file type. Please upload a JPG, PNG, WEBP or BMP image.")
    try:
        img = Image.open(file.stream)
        img.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise ImageProblem("That file doesn't look like a valid image.")
    img = ImageOps.exif_transpose(img).convert("RGB")
    if min(img.size) < 64:
        raise ImageProblem("That image is too small to analyse. Try a larger photo.")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    name = f"{uuid.uuid4().hex}.jpg"
    path = UPLOAD_DIR / name
    img.save(path, "JPEG", quality=92)
    return name, path


def _thumb_url(scan):
    processed = PROCESSED_DIR / f"scan_{scan['id']}.jpg"
    if processed.exists():
        return url_for("processed_file", filename=processed.name)
    return url_for("uploaded_file", filename=scan["image_filename"])


# ---------- routes ----------
@app.get("/")
def index():
    stats = db.get_stats()
    recent = db.recent_scans(8)
    for s in recent:
        s["thumb"] = _thumb_url(s)

    preferred = ["laptop", "cell phone", "bottle", "backpack", "calculator", "book"]
    examples = [f"Where is my {detector.display_name(c).lower()}?"
                for c in preferred if c in detector.SUPPORTED][:4]
    return render_template(
        "index.html", stats=stats, recent=recent, examples=examples,
        supported=[detector.display_name(c) for c in detector.SUPPORTED],
        model_name=detector.MODEL_NAME, max_mb=MAX_UPLOAD_MB,
    )


@app.post("/scan")
def scan():
    location = " ".join(request.form.get("location", "").split())[:60]
    if not location:
        flash("Please enter a location label, for example 'Study Desk'.", "error")
        return redirect(url_for("index") + "#scan")

    try:
        name, path = save_upload(request.files.get("image"))
    except ImageProblem as exc:
        flash(str(exc), "error")
        return redirect(url_for("index") + "#scan")

    try:
        detections = detector.detect(path)
    except (detector.ModelUnavailable, detector.DetectionError) as exc:
        path.unlink(missing_ok=True)
        flash(str(exc), "error")
        return redirect(url_for("index") + "#scan")

    try:
        scan_id = db.create_scan(name, location, detections)
    except db.DatabaseError:
        path.unlink(missing_ok=True)
        flash("Could not save this scan to the memory database. Please try again.", "error")
        return redirect(url_for("index") + "#scan")

    try:
        detector.annotate(path, detections, PROCESSED_DIR / f"scan_{scan_id}.jpg")
    except Exception:  # annotation is cosmetic; never fail the scan because of it
        app.logger.exception("Could not draw annotated image")

    return redirect(url_for("scan_detail", scan_id=scan_id))


@app.get("/scan/<int:scan_id>")
def scan_detail(scan_id):
    scan_row = db.get_scan(scan_id)
    if not scan_row:
        abort(404)
    detections = db.get_detections(scan_id)

    summary = OrderedDict()
    for d in detections:  # already sorted by confidence
        item = summary.setdefault(d["object_name"], {"name": d["object_name"], "count": 0, "best": 0})
        item["count"] += 1
        item["best"] = max(item["best"], d["confidence"])

    return render_template(
        "scan.html", scan=scan_row, detections=detections,
        summary=list(summary.values()), image_url=_thumb_url(scan_row),
    )


@app.get("/search")
def search():
    query = request.args.get("q", "").strip()
    parsed = extract_object(query)
    if parsed["status"] == "empty":
        flash("Type what you're looking for, for example 'Where is my laptop?'", "error")
        return redirect(url_for("index"))

    supported = [detector.display_name(c) for c in detector.SUPPORTED]

    if parsed["status"] == "unsupported":
        return render_template("result.html", state="unsupported", query=query,
                               term=parsed["term"], supported=supported)

    obj = parsed["object"]
    sightings = db.find_sightings(obj)
    if not sightings:
        return render_template("result.html", state="not_found", query=query,
                               object_label=detector.display_name(obj))

    best = sightings[0]
    hit_name = f"hit_{best['detection_id']}.jpg"
    hit_path = PROCESSED_DIR / hit_name
    source = UPLOAD_DIR / best["image_filename"]
    if not hit_path.exists() and source.exists():
        detector.annotate(source, [best], hit_path)
    evidence_url = url_for("processed_file", filename=hit_name) if hit_path.exists() else None

    return render_template(
        "result.html", state="found", query=query,
        object_label=detector.display_name(obj),
        hit=best, evidence_url=evidence_url,
        confidence_pct=round(best["confidence"] * 100),
        history=sightings[1:],
    )


@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.get("/processed/<path:filename>")
def processed_file(filename):
    return send_from_directory(PROCESSED_DIR, filename)


@app.get("/health")
def health():
    """Open http://127.0.0.1:5000/health to verify the AI model loads (and on which device)."""
    try:
        return jsonify(status="ok", **detector.model_info())
    except detector.ModelUnavailable as exc:
        return jsonify(status="error", message=str(exc)), 503


# ---------- friendly errors ----------
@app.errorhandler(413)
def too_large(_):
    flash(f"That image is too large. Maximum size is {MAX_UPLOAD_MB} MB.", "error")
    return redirect(url_for("index") + "#scan")


@app.errorhandler(db.DatabaseError)
def database_error(exc):
    app.logger.error("Database error: %s", exc)
    return render_template("error.html", message="The memory database had a problem. "
                           "Please try again."), 500


@app.errorhandler(Exception)
def unexpected(exc):
    if isinstance(exc, HTTPException):
        return exc
    app.logger.exception("Unexpected error")
    return render_template("error.html", message="Something went wrong on our side. "
                           "Please try again."), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
