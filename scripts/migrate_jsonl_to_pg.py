"""One-off migration: import legacy JSON/JSONL files into PostgreSQL."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import get_settings
from app.db.models.contact_request import ContactRequestModel
from app.db.models.idempotency_key import IdempotencyKeyModel
from app.db.session import get_session_factory


async def migrate_requests(data_dir: Path) -> int:
    path = data_dir / "requests.jsonl"
    if not path.exists():
        return 0
    count = 0
    async with get_session_factory()() as session:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            existing = await session.scalar(
                select(ContactRequestModel).where(
                    ContactRequestModel.request_id == rec["request_id"]
                )
            )
            if existing:
                continue
            session.add(
                ContactRequestModel(
                    request_id=rec["request_id"],
                    client_ip=rec.get("client_ip", "0.0.0.0"),
                    name=rec["name"],
                    email=rec["email"],
                    phone=rec["phone"],
                    comment=rec["comment"],
                    status=rec.get("status", "processed"),
                    sentiment=rec.get("sentiment"),
                    category=rec.get("category"),
                    summary=rec.get("summary"),
                    ai_used=rec.get("ai_used"),
                    ai_provider=rec.get("provider"),
                    email_queued=rec.get("email_owner_sent") is not None,
                )
            )
            count += 1
        await session.commit()
    return count


async def migrate_idempotency(data_dir: Path) -> int:
    path = data_dir / "idempotency.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    async with get_session_factory()() as session:
        for key, entry in data.items():
            if await session.get(IdempotencyKeyModel, key):
                continue
            created = datetime.fromtimestamp(entry["created_at"], tz=timezone.utc)
            session.add(
                IdempotencyKeyModel(
                    key=key,
                    body_hash=entry["body_hash"],
                    response=entry["response"],
                    created_at=created,
                    expires_at=created + timedelta(hours=24),
                )
            )
            count += 1
        await session.commit()
    return count


async def main() -> None:
    settings = get_settings()
    data_dir = settings.data_dir
    req_count = await migrate_requests(data_dir)
    idem_count = await migrate_idempotency(data_dir)
    print(f"Migrated {req_count} contact requests and {idem_count} idempotency keys.")


if __name__ == "__main__":
    asyncio.run(main())
