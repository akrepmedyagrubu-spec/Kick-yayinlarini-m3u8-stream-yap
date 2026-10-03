import asyncio
import os
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

OUT = Path(os.getenv("HLS_DIR", "/tmp/kick-hls"))
OUT.mkdir(parents=True, exist_ok=True)
stop_event = asyncio.Event()
process: asyncio.subprocess.Process | None = None


def valid_kick_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in {"kick.com", "www.kick.com"} and bool(re.fullmatch(r"/[A-Za-z0-9_./-]+/?", parsed.path))


async def retry_delay():
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=20)
    except asyncio.TimeoutError:
        pass


async def stream_forever():
    global process
    url = os.getenv("KICK_URL", "").strip()
    if not valid_kick_url(url):
        return
    while not stop_event.is_set():
        extract = await asyncio.create_subprocess_exec(
            "yt-dlp", "--no-warnings", "--format", "best", "--get-url", url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(extract.communicate(), timeout=45)
            source = stdout.decode(errors="replace").strip().splitlines()
        except asyncio.TimeoutError:
            extract.kill()
            await extract.wait()
            source = []
        if extract.returncode == 0 and source and source[0].startswith("https://"):
            shutil.rmtree(OUT, ignore_errors=True)
            OUT.mkdir(parents=True, exist_ok=True)
            process = await asyncio.create_subprocess_exec(
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-user_agent", "Mozilla/5.0",
                "-i", source[0], "-map", "0:v:0?", "-map", "0:a:0?", "-c", "copy",
                "-f", "hls", "-hls_time", "4", "-hls_list_size", "8",
                "-hls_flags", "delete_segments+append_list+omit_endlist+independent_segments",
                "-hls_segment_filename", str(OUT / "segment_%06d.ts"), str(OUT / "index.m3u8"),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await process.wait()
            process = None
        await retry_delay()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(stream_forever())
    yield
    stop_event.set()
    if process and process.returncode is None:
        process.terminate()
    task.cancel()


app = FastAPI(title="Kick HLS Relay", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def home():
    return """<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kick HLS</title><style>body{font:16px system-ui;max-width:650px;margin:12vh auto;padding:0 20px;color:#222}code{word-break:break-all}</style><h1>Kick HLS yayını</h1><p>Yayın Render servisi açıldığında otomatik başlar.</p><p>Sabit m3u8 adresi: <code id="url"></code></p><p id="status">Yayın kontrol ediliyor…</p><script>document.getElementById('url').textContent=location.origin+'/live/index.m3u8';fetch('/status').then(r=>r.json()).then(d=>document.getElementById('status').textContent=d.configured?(d.running?'Yayın aktif.':'Kick yayını bekleniyor veya yeniden bağlanıyor.'):'Render ortam değişkeni KICK_URL ayarlanmamış.')</script></html>"""


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/status")
async def status():
    configured = valid_kick_url(os.getenv("KICK_URL", "").strip())
    playlist = OUT / "index.m3u8"
    running = bool(process and process.returncode is None and playlist.is_file())
    return {"configured": configured, "running": running, "playlist": "/live/index.m3u8" if running else None}


@app.get("/live/{filename}")
async def live(filename: str):
    if filename != "index.m3u8" and not re.fullmatch(r"segment_\d{6}\.ts", filename):
        raise HTTPException(404)
    path = OUT / filename
    if not path.is_file():
        raise HTTPException(503, "Kick yayını hazırlanıyor veya şu anda çevrimdışı.")
    media_type = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp2t"
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate", "Access-Control-Allow-Origin": "*"}
    return FileResponse(path, media_type=media_type, headers=headers)
