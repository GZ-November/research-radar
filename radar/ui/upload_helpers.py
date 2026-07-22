"""Safe persistence helpers for user-supplied manuscript files."""

from pathlib import Path
from uuid import uuid4

from radar.config import get_settings


def persist_uploaded_manuscript(uploaded) -> Path:
    safe_name = Path(uploaded.name).name
    upload_dir = get_settings().data_dir / "uploads" / str(uuid4())
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / safe_name
    upload_path.write_bytes(uploaded.getvalue())
    return upload_path
