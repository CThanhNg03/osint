import base64
import os
import time
import uuid
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Tuple

import cv2
import uvicorn
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import Column, String, Text, JSON as SQLJSON, DateTime, func, cast
from pgvector.sqlalchemy import Vector

from ingestion_queue import IngestionQueue
from embedding_utils import generate_embedding
from database import Base, engine, SessionLocal

app = FastAPI(title="Person Embed Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

IMAGE_STORE = Path(os.getenv("IMAGE_STORE_PATH", "/data/images"))
IMAGE_STORE.mkdir(parents=True, exist_ok=True)

PEOPLE_STORE = Path(os.getenv("PEOPLE_STORE_PATH", "/data/people"))
PEOPLE_STORE.mkdir(parents=True, exist_ok=True)

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
FACE_EMBEDDING_DIM = 128

CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(CASCADE_PATH)

queue = IngestionQueue.from_env()

SFACE_MODEL_URLS = [
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    "https://github.com/opencv/opencv_zoo/raw/master/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
]
SFACE_MODEL_PATH = PEOPLE_STORE / "face_recognition_sface_2021dec.onnx"
_sface_net = None
_sface_error: str | None = None


class PersonRecord(Base):
    __tablename__ = "people_records"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    nationality = Column(String, nullable=True)
    date_of_birth = Column(String, nullable=True)
    id_number = Column(String, nullable=True, index=True)
    aliases = Column(SQLJSON, nullable=True)
    note = Column(Text, nullable=True)
    image = Column(String, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    face_embedding = Column(Vector(FACE_EMBEDDING_DIM), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Ensure table exists
try:
    Base.metadata.create_all(bind=engine)
except Exception as exc:
    print(f"[PersonService] Warning: could not initialize DB tables: {exc}")


class FaceSelection(BaseModel):
    request_id: str
    face_id: str


def detect_faces(image_bytes: bytes) -> Tuple[List[tuple], np.ndarray]:
    np_arr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Unable to decode image")
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)
    return faces, frame


def _pad_bbox(x: int, y: int, w: int, h: int, width: int, height: int, margin: float = 0.2):
    pad_w = int(w * margin)
    pad_h = int(h * margin)
    x1 = max(0, x - pad_w)
    y1 = max(0, y - pad_h)
    x2 = min(width, x + w + pad_w)
    y2 = min(height, y + h + pad_h)
    return x1, y1, x2 - x1, y2 - y1


def _save_context(request_id: str, image_path: str, faces: List[dict]):
    if not queue:
        return
    queue.client.setex(f"faces:{request_id}", 3600, json.dumps({"image_path": image_path, "faces": faces}))


def _load_context(request_id: str):
    if not queue:
        return None
    raw = queue.client.get(f"faces:{request_id}")
    if not raw:
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _lookup_person(face_id: str):
    # Placeholder DB lookup; connect to a face embedding DB here.
    return None


def _people_index_path() -> Path:
    return PEOPLE_STORE / "people_index.json"


def _load_people() -> list:
    db = SessionLocal()
    try:
        recs = db.query(PersonRecord).order_by(PersonRecord.created_at.desc()).all()
        return [_person_to_dict(r) for r in recs]
    finally:
        db.close()


def _load_mock_social_graph() -> dict:
    mock_path = Path(__file__).parent / "mock_social_graph.json"
    if not mock_path.exists():
        return {
            "source": "mock",
            "accounts": [],
            "posts": [],
            "edges": [],
            "mock": True,
        }
    try:
        with open(mock_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "source": "mock",
            "accounts": [],
            "posts": [],
            "edges": [],
            "mock": True,
        }


def _crawl_x_for_person(name: str) -> dict | None:
    token = os.getenv("X_BEARER_TOKEN")
    if not token:
        return None
    query = urllib.parse.quote(name)
    url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results=10&tweet.fields=author_id,created_at,text"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status != 200:
                return None
            payload = json.loads(resp.read().decode("utf-8"))
            return payload
    except Exception:
        return None


def _search_x_accounts(name: str) -> list[dict]:
    """Search X/Twitter accounts by name (best effort). Returns list of account dicts."""
    token = os.getenv("X_BEARER_TOKEN")
    if not token:
        return []
    query = urllib.parse.quote(name)
    url = f"https://api.twitter.com/2/users/by?usernames={query}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status != 200:
                return []
            payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data") or []
            return [
                {
                    "id": u.get("id"),
                    "handle": f"@{u.get('username')}" if u.get("username") else None,
                    "display_name": u.get("name") or u.get("username"),
                }
                for u in data
            ]
    except Exception:
        return []


def _build_social_graph(person: dict, force_mock: bool = False) -> dict:
    """Build a simple graph of the person's X presence; falls back to mock data."""
    mock_graph = _load_mock_social_graph()
    # If person name matches mock, always return mock graph
    mock_name = (mock_graph.get("person_name") or "").strip().lower()
    person_name = (person.get("name") or person.get("id") or "").strip().lower()
    use_mock = force_mock or (mock_name and person_name and mock_name == person_name)

    if use_mock:
        graph = mock_graph
    else:
        # Try account search
        accounts = _search_x_accounts(person.get("name") or person.get("id") or "")
        # Pull recent tweets as posts
        payload = _crawl_x_for_person(person.get("name") or person.get("id") or "")
        posts = []
        edges = []
        if payload and payload.get("data"):
            for t in payload["data"]:
                acc_id = t.get("author_id") or (accounts[0]["id"] if accounts else "unknown")
                if acc_id and not any(a.get("id") == acc_id for a in accounts):
                    accounts.append({"id": acc_id, "handle": f"@user_{acc_id}", "display_name": acc_id})
                posts.append(
                    {
                        "id": t.get("id"),
                        "account_id": acc_id,
                        "text": t.get("text"),
                        "timestamp": t.get("created_at"),
                    }
                )
                edges.append({"source": person.get("id"), "target": acc_id, "type": "mentioned_in"})
        if not accounts:
            mock = _load_mock_social_graph()
            accounts = mock.get("accounts", [])
            posts = mock.get("posts", [])
            edges = mock.get("edges", [])

        primary_account_id = accounts[0]["id"] if accounts else None
        graph = {
            "source": "x",
            "person_id": person.get("id"),
            "person_name": person.get("name"),
            "accounts": accounts,
            "primary_account_id": primary_account_id,
            "posts": posts,
            "edges": edges,
            "mock": not bool(payload),
        }

    # Attach person linkage to all edges
    for edge in graph.get("edges", []):
        edge.setdefault("person_id", person.get("id"))
        edge.setdefault("person_name", person.get("name"))
    graph.setdefault("person_id", person.get("id"))
    graph.setdefault("person_name", person.get("name"))
    return graph


def _save_people(entries: list) -> None:
    # Deprecated JSON store; kept for compatibility but unused in DB mode.
    idx_path = _people_index_path()
    idx_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), "utf-8")


def _find_person(person_id: str) -> dict | None:
    db = SessionLocal()
    try:
        rec = db.query(PersonRecord).filter(PersonRecord.id == person_id).first()
        if not rec:
            return None
        return _person_to_dict(rec)
    finally:
        db.close()


def _person_to_dict(rec: PersonRecord) -> dict:
    def _clean_vec(val):
        if val is None:
            return None
        if isinstance(val, memoryview):
            try:
                val = val.tobytes()
            except Exception:
                return None
        if hasattr(val, "tolist"):
            try:
                val = val.tolist()
            except Exception:
                return None
        if isinstance(val, (bytes, bytearray)):
            try:
                val = list(np.frombuffer(val, dtype=float))
            except Exception:
                return None
        if isinstance(val, (list, tuple)):
            try:
                return [float(x) for x in val]
            except Exception:
                return list(val)
        return None

    return {
        "id": rec.id,
        "name": rec.name,
        "nationality": rec.nationality,
        "date_of_birth": rec.date_of_birth,
        "id_number": rec.id_number,
        "aliases": rec.aliases or [],
        "note": rec.note,
        "image": rec.image,
        "embedding": _clean_vec(rec.embedding),
        "face_embedding": _clean_vec(rec.face_embedding),
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
    }


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return -1.0
    return float(np.dot(va, vb) / denom)


@app.middleware("http")
async def audit_requests(request: Request, call_next):
    """Lightweight request audit to trace person-service traffic."""
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(
            f"[PersonService] {request.method} {request.url.path} "
            f"status={status_code} time_ms={elapsed_ms:.1f}"
        )


def _ensure_sface():
    global _sface_net, _sface_error
    if _sface_net is not None or _sface_error:
        return _sface_net
    try:
        if not SFACE_MODEL_PATH.exists():
            SFACE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            last_exc = None
            for url in SFACE_MODEL_URLS:
                try:
                    urllib.request.urlretrieve(url, SFACE_MODEL_PATH)
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
            if last_exc:
                raise last_exc
        _sface_net = cv2.dnn.readNet(str(SFACE_MODEL_PATH))
    except Exception as exc:
        _sface_error = str(exc)
        print(f"[PersonService] Failed to load SFace model: {exc}")
        _sface_net = None
    return _sface_net


def _face_embedding_from_bbox(frame: np.ndarray, bbox: tuple[int, int, int, int]) -> list[float]:
    net = _ensure_sface()
    if net is None:
        return []
    x, y, w, h = bbox
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return []
    blob = cv2.dnn.blobFromImage(crop, scalefactor=1 / 255.0, size=(112, 112), mean=(0, 0, 0), swapRB=True)
    try:
        net.setInput(blob)
        feat = net.forward()
        vec = feat.flatten()
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.astype(float).tolist()
    except Exception as exc:
        print(f"[PersonService] Face embedding failed: {exc}")
        return []


@app.post("/image/detect")
async def detect_image(file: UploadFile = File(...)):
    if not queue:
        raise HTTPException(status_code=503, detail="REDIS_URL is required for face session storage")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image")

    try:
        faces, frame = detect_faces(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Detection failed: {exc}") from exc

    image_id = str(uuid.uuid4())
    image_path = IMAGE_STORE / f"{image_id}.jpg"
    with open(image_path, "wb") as f:
        f.write(data)

    faces_payload = []
    h_img, w_img = frame.shape[:2]

    for idx, (x, y, w, h) in enumerate(faces):
        px, py, pw, ph = _pad_bbox(int(x), int(y), int(w), int(h), w_img, h_img, margin=0.2)
        crop = frame[py : py + ph, px : px + pw]
        preview_b64 = ""
        try:
            _, buf = cv2.imencode(".jpg", crop)
            preview_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
        except Exception:
            preview_b64 = ""
        faces_payload.append(
            {
                "face_id": f"{image_id}-{idx}",
                "bbox": [int(px), int(py), int(pw), int(ph)],
                "preview": preview_b64,  # base64-encoded JPEG of the face crop with margin
            }
        )

    _save_context(image_id, str(image_path), faces_payload)

    if len(faces_payload) == 0:
        return {"status": "no_face", "message": "No human detected", "image_id": image_id}
    if len(faces_payload) > 1:
        return {
            "status": "choose_face",
            "message": "Multiple humans detected. Please choose one face_id.",
            "request_id": image_id,
            "faces": faces_payload,
        }

    # Single face: attempt lookup immediately
    person = _lookup_person(faces_payload[0]["face_id"])
    return {
        "status": "ok",
        "request_id": image_id,
        "face": faces_payload[0],
        "person": person or {"matched": False, "note": "No record found"},
    }


@app.post("/image/select")
async def select_face(selection: FaceSelection):
    if not queue:
        raise HTTPException(status_code=503, detail="REDIS_URL is required for face session storage")
    ctx = _load_context(selection.request_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Request expired or not found")
    face = next((f for f in ctx.get("faces", []) if f["face_id"] == selection.face_id), None)
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")

    person = _lookup_person(selection.face_id)
    return {
        "status": "ok",
        "request_id": selection.request_id,
        "face": face,
        "person": person or {"matched": False, "note": "No record found"},
    }


@app.get("/people")
async def list_people():
    try:
        return _load_people()
    except Exception as exc:
        print(f"[PersonService] Failed to serialize people: {exc}")
        raise


@app.post("/people")
async def add_person(
    name: str = Form(...),
    nationality: str = Form(""),
    date_of_birth: str = Form(""),  # ISO-like string
    id_number: str = Form(""),
    aliases: str = Form(""),
    note: str = Form(""),
    file: UploadFile = File(...),
):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Name is required")

    person_id = str(uuid.uuid4())
    ext = Path(file.filename or "").suffix or ".jpg"
    img_path = PEOPLE_STORE / f"{person_id}{ext}"

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image")
    img_path.write_bytes(data)

    aliases_list = [a.strip() for a in aliases.split(",") if a.strip()] if aliases else []

    # Compute face embedding from the first detected face in the uploaded photo
    face_embed: list[float] = []
    try:
        faces, frame = detect_faces(data)
        if len(faces) > 0:
            x, y, w, h = faces[0]
            px, py, pw, ph = _pad_bbox(int(x), int(y), int(w), int(h), frame.shape[1], frame.shape[0], margin=0.2)
            face_embed = _face_embedding_from_bbox(frame, (px, py, pw, ph))
    except Exception as exc:
        print(f"[PersonService] Face embedding skipped: {exc}")

    bio_text = "\n".join(
        filter(
            None,
            [
                f"Name: {name}",
                f"Nationality: {nationality}",
                f"Date of birth: {date_of_birth}",
                f"ID: {id_number}",
                f"Aliases: {', '.join(aliases_list)}" if aliases_list else "",
                f"Note: {note}",
            ],
        )
    )
    embedding = generate_embedding(bio_text) if bio_text else []
    if not embedding or len(embedding) != EMBEDDING_DIM:
        embedding = None

    entry = {
        "id": person_id,
        "name": name.strip(),
        "nationality": nationality.strip(),
        "date_of_birth": date_of_birth.strip(),
        "id_number": id_number.strip(),
        "aliases": aliases_list,
        "note": note.strip(),
        "image": img_path.name,
        "face_embedding": face_embed if face_embed and len(face_embed) == FACE_EMBEDDING_DIM else None,
        "embedding": embedding,
    }
    db = SessionLocal()
    try:
        rec = PersonRecord(
            id=person_id,
            name=entry["name"],
            nationality=entry["nationality"],
            date_of_birth=entry["date_of_birth"],
            id_number=entry["id_number"],
            aliases=entry["aliases"],
            note=entry["note"],
            image=entry["image"],
            embedding=entry["embedding"],
            face_embedding=entry["face_embedding"],
        )
        db.add(rec)
        db.commit()
    finally:
        db.close()
    return entry


@app.get("/people/{person_id}")
async def get_person(person_id: str):
    person = _find_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Not found")
    return person


@app.delete("/people/{person_id}")
async def delete_person(person_id: str):
    db = SessionLocal()
    try:
        rec = db.query(PersonRecord).filter(PersonRecord.id == person_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Not found")
        db.delete(rec)
        db.commit()
    finally:
        db.close()
    # Remove image file
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        img_path = PEOPLE_STORE / f"{person_id}{ext}"
        if img_path.exists():
            try:
                img_path.unlink()
            except Exception:
                pass
    return {"status": "deleted", "id": person_id}


@app.get("/people/{person_id}/image")
async def person_image(person_id: str):
    person = _find_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Not found")
    img_name = person.get("image")
    if not img_name:
        raise HTTPException(status_code=404, detail="Image not found")
    path = PEOPLE_STORE / img_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


@app.get("/people/search")
async def search_people(q: str, limit: int = 5, include_social: bool = False):
    """Semantic search over people bios using embeddings."""
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query required")
    q_embed = generate_embedding(query)
    if not q_embed:
        raise HTTPException(status_code=500, detail="Embedding unavailable")

    db = SessionLocal()
    try:
        dist_expr = func.cosine_distance(PersonRecord.embedding, cast(q_embed, Vector(EMBEDDING_DIM)))
        rows = (
            db.query(PersonRecord, dist_expr.label("dist"))
            .filter(PersonRecord.embedding != None)  # noqa: E711
            .order_by(dist_expr)
            .limit(max(1, min(limit, 20)))
            .all()
        )
        threshold = 0.50
        results = []
        for rec, dist in rows:
            if dist is None:
                continue
            score = 1 - float(dist)
            if score < threshold:
                continue
            results.append({**_person_to_dict(rec), "score": score})
        if include_social and results:
            results[0]["social_graph"] = _build_social_graph(results[0])
        return {"results": results, "count": len(results)}
    finally:
        db.close()


@app.post("/people/search/face")
async def search_people_face(file: UploadFile = File(...), limit: int = 5, include_social: bool = False):
    """Search people by face embedding."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image")
    try:
        faces, frame = detect_faces(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Detection failed: {exc}") from exc

    if len(faces) == 0:
        raise HTTPException(status_code=400, detail="No face detected")

    # Use the first detected face for now
    x, y, w, h = faces[0]
    px, py, pw, ph = _pad_bbox(int(x), int(y), int(w), int(h), frame.shape[1], frame.shape[0], margin=0.2)
    query_embed = _face_embedding_from_bbox(frame, (px, py, pw, ph))
    if not query_embed:
        raise HTTPException(status_code=500, detail="Face embedding unavailable")

    db = SessionLocal()
    try:
        dist_expr = func.cosine_distance(PersonRecord.face_embedding, cast(query_embed, Vector(FACE_EMBEDDING_DIM)))
        rows = (
            db.query(PersonRecord, dist_expr.label("dist"))
            .filter(PersonRecord.face_embedding != None) 
            .order_by(dist_expr)
            .limit(max(1, min(limit, 20)))
            .all()
        )
        threshold = 0.85
        best_match = None
        for rec, dist in rows:
            if dist is None:
                continue
            score = 1 - float(dist)
            if score < threshold:
                continue
            best_match = {**_person_to_dict(rec), "score": score}
            break
        if not best_match:
            return {"result": None, "threshold": threshold, "message": "No match above threshold"}
        if include_social:
            best_match["social_graph"] = _build_social_graph(best_match)
        return {"result": best_match, "threshold": threshold}
    finally:
        db.close()


@app.get("/people/{person_id}/social-crawl")
async def social_crawl(person_id: str, confirm: bool = False):
    """Prepare or build social graph for a person (name-based X lookup/mock)."""
    person = _find_person(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    graph = _build_social_graph(person, force_mock=not confirm)
    primary_account = None
    if graph.get("accounts"):
        primary_account = graph["accounts"][0]
    return {
        "person": person,
        "social_graph": graph,
        "primary_account": primary_account,
        "status": "ready" if confirm else "preview",
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PERSON_SERVICE_PORT", "8001")))
