import asyncio
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Kick HLS Relay")
OUT = Path(os.getenv("HLS_DIR", "/tmp/kick-hls"))
OUT.mkdir(parents=True, exist_ok=True)
process: asyncio.subprocess.Process | None = None
active_url: str | None = None
log_task: asyncio.Task | None = None


class StartRequest(BaseModel):
    url: str
    token: str


class StopRequest(BaseModel):
    token: str


def valid_kick_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in {"kick.com", "www.kick.com"} and bool(re.fullmatch(r"/[A-Za-z0-9_./-]+/?", parsed.path))


def authorize(token: str | None):
    expected = os.getenv("ADMIN_TOKEN", "")
    if len(expected) < 16:
        raise HTTPException(503, "ADMIN_TOKEN Render ortam değişkeninde en az 16 karakter olmalı.")
    if not token or not __import__("hmac").compare_digest(token, expected):
        raise HTTPException(401, "Geçersiz yönetici tokenı.")


async def drain_output(stream):
    while await stream.readline():
        pass


async def stop_process():
    global process, active_url
    if process and process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=8)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
    process = None
    active_url = None


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML


@app.get("/health")
async def health():
    return {"ok": True, "running": bool(process and process.returncode is None)}


@app.get("/status")
async def status():
    running = bool(process and process.returncode is None)
    return {"running": running, "source": active_url if running else None, "playlist": "/live/index.m3u8" if running else None}


@app.post("/api/start")
async def start(req: StartRequest):
    global process, active_url, log_task
    authorize(req.token)
    if not valid_kick_url(req.url):
        raise HTTPException(400, "https://kick.com/kanal biçiminde geçerli bir Kick kanal bağlantısı girin.")
    if not shutil.which("ffmpeg") or not shutil.which("yt-dlp"):
        raise HTTPException(500, "Sunucuda yt-dlp veya ffmpeg bulunamadı.")
    await stop_process()
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True, exist_ok=True)
    # Resolve the current signed source URL each time the operator starts a stream.
    extract = await asyncio.create_subprocess_exec(
        "yt-dlp", "--no-warnings", "--format", "best", "--get-url", req.url,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(extract.communicate(), timeout=45)
    except asyncio.TimeoutError:
        extract.kill()
        await extract.wait()
        raise HTTPException(504, "Kick yayın adresi zaman aşımına uğradı.")
    source = stdout.decode(errors="replace").strip().splitlines()
    if extract.returncode or not source or not source[0].startswith("https://"):
        reason = stderr.decode(errors="replace")[-500:]
        raise HTTPException(502, "Kick yayını alınamadı. Kanal canlı olmayabilir veya Kick erişimi değişmiş olabilir. " + reason)
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-user_agent", "Mozilla/5.0",
        "-i", source[0], "-map", "0:v:0?", "-map", "0:a:0?", "-c", "copy",
        "-f", "hls", "-hls_time", "4", "-hls_list_size", "8",
        "-hls_flags", "delete_segments+append_list+omit_endlist+independent_segments",
        "-hls_segment_filename", str(OUT / "segment_%06d.ts"), str(OUT / "index.m3u8"),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    log_task = asyncio.create_task(drain_output(process.stderr))
    active_url = req.url
    await asyncio.sleep(1)
    if process.returncode is not None:
        await stop_process()
        raise HTTPException(502, "FFmpeg yayını başlatamadı. URL veya yayın biçimi desteklenmiyor olabilir.")
    return {"ok": True, "playlist": "/live/index.m3u8"}


@app.post("/api/stop")
async def stop(req: StopRequest):
    authorize(req.token)
    await stop_process()
    return {"ok": True}


@app.get("/live/{filename}")
async def live(filename: str):
    if filename != "index.m3u8" and not re.fullmatch(r"segment_\d{6}\.ts", filename):
        raise HTTPException(404)
    path = OUT / filename
    if not path.is_file():
        raise HTTPException(503, "Yayın hazırlanıyor veya çalışmıyor.")
    media_type = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp2t"
    headers = {"Cache-Control": "no-store, no-cache, must-revalidate", "Access-Control-Allow-Origin": "*"}
    return FileResponse(path, media_type=media_type, headers=headers)


HTML = """<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kick HLS Relay</title>
<style>body{font:16px system-ui;max-width:680px;margin:7vh auto;padding:0 20px;color:#202124}input,button{font:inherit;padding:12px;margin:6px 0;width:100%;box-sizing:border-box}button{background:#53fc18;border:0;border-radius:6px;cursor:pointer;font-weight:700}.stop{background:#eee}code{word-break:break-all}.muted{color:#666}</style>
<h1>Kick → HLS</h1><p class="muted">Kick kanal bağlantısını ve Render’da belirlediğin yönetici tokenını gir.</p>
<input id="url" placeholder="https://kick.com/kanal"><input id="token" type="password" placeholder="ADMIN_TOKEN">
<button onclick="start()">Yayını başlat</button><button class="stop" onclick="stop()">Yayını durdur</button><p id="msg"></p><p>Sabit yayın adresi: <code id="playlist">—</code></p>
<script>const $=id=>document.getElementById(id);async function call(path){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:$('url').value,token:$('token').value})});let d=await r.json();if(!r.ok)throw Error(d.detail||'İşlem başarısız');return d}async function start(){try{let d=await call('/api/start');$('playlist').textContent=location.origin+d.playlist;$('msg').textContent='Yayın başladı.'}catch(e){$('msg').textContent=e.message}}async function stop(){try{await call('/api/stop');$('msg').textContent='Yayın durduruldu.'}catch(e){$('msg').textContent=e.message}}fetch('/status').then(r=>r.json()).then(d=>{if(d.running)$('playlist').textContent=location.origin+d.playlist})</script></html>"""
