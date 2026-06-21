"""
Local storage for the customer media queue.

Instagram and the OpenAI vision API both need a publicly reachable URL, so uploaded
files are saved under ``data/uploads/{customer_id}/`` and served by the API itself via
``/uploads`` (mounted in ``api.py``). ``PUBLIC_BASE_URL`` must point at a real, internet
reachable HTTPS origin in production for this to work.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import BinaryIO

from .local_media import ALL_MEDIA_EXTENSIONS, IMAGE_EXTENSIONS

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


def _public_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def save_upload(customer_id: str, filename: str, content: BinaryIO) -> tuple[str, str, str]:
    """
    Save an uploaded file for a customer's media queue.

    Returns (file_path, public_url, media_type).
    Raises ValueError if the extension isn't a supported image/video type.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALL_MEDIA_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(ALL_MEDIA_EXTENSIONS))}"
        )

    customer_dir = UPLOADS_DIR / customer_id
    customer_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = customer_dir / stored_name
    with open(dest, "wb") as f:
        f.write(content.read())

    media_type = "image" if ext in IMAGE_EXTENSIONS else "video"
    public_url = f"{_public_base_url()}/uploads/{customer_id}/{stored_name}"
    return str(dest), public_url, media_type


def delete_upload(file_path: str) -> bool:
    """Best-effort delete of a stored file."""
    try:
        Path(file_path).unlink(missing_ok=True)
        return True
    except OSError:
        return False
