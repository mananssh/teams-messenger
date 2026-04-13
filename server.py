"""FastAPI server for the Meeting Assistant web UI.

Run with:  python server.py          (defaults to http://localhost:8000)
   or:     uvicorn server:app --reload
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Empty
from threading import Thread

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.config import Settings
from app.models import AttendanceRecord

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"

app = FastAPI(title="Meeting Assistant")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/config")
async def get_config():
    s = Settings()
    return {
        "enable_teams": s.enable_teams,
        "enable_email": s.enable_email,
        "enable_jira": s.enable_jira,
        "enable_github": s.enable_github,
    }


@app.post("/api/run")
async def run_pipeline(
    mode: str = Form(...),
    file: UploadFile = File(...),
    participants: UploadFile | None = File(None),
):
    settings = Settings()
    event_queue: Queue = Queue()

    def on_event(event_type: str, data: dict):
        event_queue.put((event_type, data))

    file_bytes = await file.read()
    participants_bytes = await participants.read() if participants else None

    on_event("step", {"id": "upload", "status": "done",
                      "detail": f"Received {file.filename}" + (f" + participants" if participants_bytes else "")})

    def pipeline_thread():
        try:
            _run_in_thread(
                mode=mode,
                file_bytes=file_bytes,
                filename=file.filename or "upload",
                participants_bytes=participants_bytes,
                settings=settings,
                on_event=on_event,
            )
        except Exception as exc:
            logger.exception("Pipeline thread failed")
            on_event("error", {"detail": str(exc)})
        finally:
            on_event("__done__", {})

    thread = Thread(target=pipeline_thread, daemon=True)
    thread.start()

    async def event_generator():
        while True:
            try:
                event_type, data = event_queue.get(timeout=0.1)
            except Empty:
                await asyncio.sleep(0.05)
                continue

            if event_type == "__done__":
                yield {"event": "done", "data": "{}"}
                return

            yield {"event": event_type, "data": json.dumps(data, default=str)}

    return EventSourceResponse(event_generator())


def _run_in_thread(
    *,
    mode: str,
    file_bytes: bytes,
    filename: str,
    participants_bytes: bytes | None,
    settings: Settings,
    on_event,
):
    meeting_id = "mtg-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        file_path = tmp / filename
        file_path.write_bytes(file_bytes)

        if mode == "audio":
            from app.transcription.whisper_service import transcribe_audio

            if not participants_bytes:
                on_event("error", {"detail": "Audio mode requires participants JSON"})
                return

            on_event("step", {"id": "transcribe", "status": "running",
                              "detail": "Transcribing audio with Whisper…"})

            transcript = transcribe_audio(file_path, model_name=settings.whisper_model)
            if not transcript:
                on_event("step", {"id": "transcribe", "status": "error",
                                  "detail": "Transcription produced no output"})
                return

            on_event("step", {"id": "transcribe", "status": "done",
                              "detail": f"{len(transcript)} chars transcribed"})

            raw = json.loads(participants_bytes)
            participant_list = [AttendanceRecord.model_validate(r) for r in raw]

        elif mode == "transcript":
            from app.transcription.vtt_parser import parse_vtt

            on_event("step", {"id": "transcribe", "status": "running",
                              "detail": "Parsing VTT transcript…"})

            result = parse_vtt(file_path)
            if result is None:
                on_event("step", {"id": "transcribe", "status": "error",
                                  "detail": "Failed to parse VTT file"})
                return

            transcript = result.text

            if participants_bytes:
                raw = json.loads(participants_bytes)
                participant_list = [AttendanceRecord.model_validate(r) for r in raw]
            else:
                participant_list = result.participants

            on_event("step", {"id": "transcribe", "status": "done",
                              "detail": f"{len(transcript)} chars, {len(participant_list)} participants"})
        else:
            on_event("error", {"detail": f"Unknown mode: {mode}"})
            return

        from app.pipeline import run

        analysis = run(
            transcript,
            participants=participant_list,
            meeting_id=meeting_id,
            settings=settings,
            on_event=on_event,
        )

        if analysis:
            on_event("result", json.loads(analysis.model_dump_json()))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
