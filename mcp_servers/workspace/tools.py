"""Workspace: calendar slots, tentative holds, email drafts. Local mock backing (no Google creds needed);
the agent only ever sees MCP tools. Swap the mock for Google Calendar/Gmail behind the same methods."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated

from pydantic import BaseModel, Field

Key = Annotated[str, Field(min_length=8, max_length=64)]


class Slot(BaseModel):
    start: str
    end: str


class SlotList(BaseModel):
    slots: list[Slot]


class HoldOut(BaseModel):
    hold_id: str
    start: str
    status: str = "tentative"
    replayed: bool = False


class EmailDraftOut(BaseModel):
    draft_id: str
    status: str = "draft"      # never sent: a human sends from their mail client
    replayed: bool = False


class WorkspaceService:
    BUSY = {"10:00"}  # a standing meeting every working day, so "free" is not trivially everything

    def __init__(self, work_start: int = 10, work_end: int = 16):
        self.work_start, self.work_end = work_start, work_end
        self.holds: dict[str, dict] = {}
        self.emails: dict[str, dict] = {}

    async def get_free_slots(self, start_date: str, days: int = 5, duration_minutes: int = 30, limit: int = 5) -> SlotList:
        d0, out = date.fromisoformat(start_date), []
        taken = {h["start"] for h in self.holds.values()}
        for n in range(days):
            day = d0 + timedelta(days=n)
            if day.weekday() >= 5:
                continue
            t = datetime(day.year, day.month, day.day, self.work_start)
            while t.hour < self.work_end:
                s = t.isoformat(timespec="minutes")
                if t.strftime("%H:%M") not in self.BUSY and s not in taken:
                    out.append(Slot(start=s, end=(t + timedelta(minutes=duration_minutes)).isoformat(timespec="minutes")))
                t += timedelta(minutes=60)
        return SlotList(slots=out[:limit])

    async def create_tentative_hold(self, start: str, title: str, idempotency_key: str) -> HoldOut:
        if idempotency_key in self.holds:
            h = self.holds[idempotency_key]
            if h['start'] != start or h['title'] != title:
                raise ValueError('idempotency_conflict')
            return HoldOut(hold_id=h["hold_id"], start=h["start"], replayed=True)
        if start in {h["start"] for h in self.holds.values()}:
            raise ValueError("slot_taken")
        h = {"hold_id": f"hold-{len(self.holds) + 1:04d}", "start": start, "title": title}
        self.holds[idempotency_key] = h
        return HoldOut(hold_id=h["hold_id"], start=start)

    async def create_email_draft(self, to: str, subject: str, body: str, idempotency_key: str) -> EmailDraftOut:
        if idempotency_key in self.emails:
            previous = self.emails[idempotency_key]
            if any(previous[field] != value for field, value in [('to', to), ('subject', subject), ('body', body)]):
                raise ValueError('idempotency_conflict')
            return EmailDraftOut(draft_id=self.emails[idempotency_key]["draft_id"], replayed=True)
        rec = {"draft_id": f"mail-{len(self.emails) + 1:04d}", "to": to, "subject": subject, "body": body}
        self.emails[idempotency_key] = rec
        return EmailDraftOut(draft_id=rec["draft_id"])
