import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="VideoLoader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "videoloader"
DOWNLOAD_DIR.mkdir(exist_ok=True)

jobs: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Localisation de ffmpeg
# Ordre de priorite :
#   1. Variable d'environnement FFMPEG_PATH
#   2. Chemin Windows par defaut (C:\ffmpeg\bin\ffmpeg.exe)
#   3. ffmpeg dans le PATH systeme (macOS / Linux)
# ---------------------------------------------------------------------------

def find_ffmpeg():
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and Path(env_path).is_file():
        return env_path
    win_path = Path(r"C:\ffmpeg\bin\ffmpeg.exe")
    if win_path.is_file():
        return str(win_path)
    return shutil.which("ffmpeg")

FFMPEG_PATH = find_ffmpeg()


# ---------------------------------------------------------------------------
# Modele de requete
# ---------------------------------------------------------------------------

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp4"
    resolution: str = ""
    audio_only: bool = False
    audio_format: str = "mp3"


# ---------------------------------------------------------------------------
# Construction de la commande yt-dlp
# ---------------------------------------------------------------------------

def build_yt_dlp_command(job_dir: Path, req: DownloadRequest) -> list:
    # sys.executable garantit le meme Python que le serveur (evite les problemes PATH)
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--newline"]

    if FFMPEG_PATH:
        cmd += ["--ffmpeg-location", FFMPEG_PATH]

    cmd += ["-o", str(job_dir / "%(title)s.%(ext)s")]

    if req.audio_only:
        cmd += ["-x", "--audio-format", req.audio_format]
    else:
        ext = req.format if req.format in ("mp4", "webm", "mkv") else "mp4"
        if req.resolution:
            fmt = (
                f"bestvideo[height<={req.resolution}][ext={ext}]+bestaudio"
                f"/bestvideo[height<={req.resolution}]+bestaudio"
                f"/best[height<={req.resolution}]"
            )
        else:
            fmt = f"bestvideo[ext={ext}]+bestaudio/bestvideo+bestaudio/best"

        cmd += [
            "-f", fmt,
            "--merge-output-format", ext,
            "--postprocessor-args", "ffmpeg:-c:a aac",
        ]

    cmd.append(req.url)
    return cmd


# ---------------------------------------------------------------------------
# Worker de telechargement
# ---------------------------------------------------------------------------

def run_download(job_id: str, req: DownloadRequest):
    job_dir = DOWNLOAD_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    jobs[job_id]["status"] = "downloading"

    cmd = build_yt_dlp_command(job_dir, req)
    jobs[job_id]["cmd"] = " ".join(cmd)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        jobs[job_id]["pid"] = proc.pid
        log_lines = []

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            log_lines.append(line)
            jobs[job_id]["log"] = log_lines[-30:]

            m = re.search(r"\[download\]\s+([\d.]+)%", line)
            if m:
                jobs[job_id]["progress"] = float(m.group(1))

            if "[Merger]" in line or "Merging formats" in line:
                jobs[job_id]["progress"] = 99
                jobs[job_id]["status"] = "processing"

        proc.wait()

        if proc.returncode == 0:
            files = list(job_dir.iterdir())
            if files:
                jobs[job_id]["status"] = "done"
                jobs[job_id]["file"] = files[0].name
                jobs[job_id]["progress"] = 100
            else:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"] = "Aucun fichier trouve apres le telechargement."
        else:
            last_log = "\n".join(log_lines[-5:])
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = f"yt-dlp a echoue (code {proc.returncode}).\n{last_log}"

    except FileNotFoundError:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = "yt-dlp n'est pas installe. Lancez : pip install yt-dlp"
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


# ---------------------------------------------------------------------------
# Routes API
# ---------------------------------------------------------------------------

@app.post("/api/download")
def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "progress": 0, "log": [], "file": None, "error": None}
    background_tasks.add_task(run_download, job_id, req)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return {"status": "not_found"}
    return job


@app.get("/api/file/{job_id}")
def get_file(job_id: str):
    job = jobs.get(job_id)
    if not job or job["status"] != "done" or not job["file"]:
        return {"error": "Fichier non disponible"}
    path = DOWNLOAD_DIR / job_id / job["file"]
    return FileResponse(
        path=str(path),
        filename=job["file"],
        media_type="application/octet-stream",
    )


@app.delete("/api/job/{job_id}")
def delete_job(job_id: str):
    job_dir = DOWNLOAD_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    jobs.pop(job_id, None)
    return {"ok": True}


app.mount("/", StaticFiles(directory=".", html=True), name="static")
