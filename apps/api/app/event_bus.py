from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from uuid import uuid4


class RealtimeEventBus:
    """In-process provider-neutral notification fan-out for canonical events.

    PostgreSQL remains authoritative. This bus only broadcasts completed
    processing observations to connected investigator clients.
    """

    def __init__(self):
        self._queues: set[asyncio.Queue] = set()
        self._history: deque[dict] = deque(maxlen=500)
        self.last_event_at: datetime | None = None

    @property
    def connection_count(self) -> int: return len(self._queues)

    def status(self) -> dict:
        return {"connections": self.connection_count, "last_event_at": self.last_event_at, "history_size": len(self._history)}

    async def publish(self, event_type: str, *, case_id: str | None = None, wallet_id: str | None = None, transaction_hash: str | None = None, chain: str | None = None, source: str = "RRR", mode: str = "LIVE", payload: dict | None = None):
        item={"event_id":str(uuid4()),"event_type":event_type,"timestamp":datetime.now(timezone.utc).isoformat(),"case_id":case_id,"wallet_id":wallet_id,"transaction_hash":transaction_hash,"chain":chain,"source":source,"mode":mode,"payload":payload or {}}
        self.last_event_at=datetime.now(timezone.utc); self._history.append(item)
        for queue in list(self._queues):
            try: queue.put_nowait(item)
            except asyncio.QueueFull: pass
        return item

    async def subscribe(self, case_id: str | None = None, last_event_id: str | None = None):
        queue: asyncio.Queue=asyncio.Queue(maxsize=100)
        self._queues.add(queue)
        try:
            replay=list(self._history)
            if last_event_id:
                for index,item in enumerate(replay):
                    if item["event_id"]==last_event_id: replay=replay[index+1:]; break
            for item in replay:
                if not case_id or item.get("case_id")==case_id: yield item
            while True:
                try:
                    item=await asyncio.wait_for(queue.get(),timeout=15)
                    if not case_id or item.get("case_id")==case_id: yield item
                except asyncio.TimeoutError:
                    yield {"event_id":str(uuid4()),"event_type":"SYSTEM_STATUS","timestamp":datetime.now(timezone.utc).isoformat(),"case_id":case_id,"wallet_id":None,"transaction_hash":None,"chain":None,"source":"RealtimeEventBus","mode":"DEVELOPMENT_SYNTHETIC","payload":{"heartbeat":True,**self.status()}}
        finally:
            self._queues.discard(queue)
