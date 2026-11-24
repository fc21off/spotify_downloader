import hmac
import json
import os
import re
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import imageio_ffmpeg

TRACK = re.compile(r"https://open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]{22})")
MAX_MP3_BYTES = 4_400_000


class handler(BaseHTTPRequestHandler):
    def reply(self, status, message):
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        secret = os.environ.get("DOWNLOAD_PASSWORD")
        if not secret:
            return self.reply(503, "Setze DOWNLOAD_PASSWORD im Vercel-Projekt.")
        supplied = self.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied.encode(), ("Bearer " + secret).encode()):
            return self.reply(401, "Das App-Passwort stimmt nicht.")
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2048:
                raise ValueError
            payload = json.loads(self.rfile.read(size))
            link = payload["url"].strip().split("?", 1)[0].split("#", 1)[0]
            match = TRACK.fullmatch(link)
            if not match:
                raise ValueError
        except (AttributeError, KeyError, TypeError, ValueError):
            return self.reply(400, "Bitte einen Spotify-Link zu einem einzelnen Song eingeben.")

        track_id = match.group(1)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            env = {**os.environ, "HOME": directory, "XDG_CACHE_HOME": directory}
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "spotdl", "download",
                     "https://open.spotify.com/track/" + track_id,
                     "--ffmpeg", imageio_ffmpeg.get_ffmpeg_exe(),
                     "--format", "mp3", "--bitrate", "128k",
                     "--output", str(output / "{track-id}.{output-ext}")],
                    cwd=directory, env=env, capture_output=True, timeout=100, text=True, encoding="utf-8", errors="replace",
                )
            except subprocess.TimeoutExpired:
                return self.reply(504, "spotDL hat zu lange gebraucht.")
            except (OSError, RuntimeError) as error:
                print(f"spotDL start failed for {track_id}: {error}", file=sys.stderr, flush=True)
                return self.reply(502, "spotDL oder FFmpeg konnte nicht gestartet werden.")

            files = list(output.glob("*.mp3"))
            if result.returncode or len(files) != 1:
                details = "\n".join((result.stdout, result.stderr)).strip()
                print(
                    f"spotDL failed for {track_id} (exit {result.returncode}): {details[-3500:]}",
                    file=sys.stderr, flush=True,
                )
                diagnostic = details.lower()
                if "sign in to confirm" in diagnostic or "not a bot" in diagnostic:
                    return self.reply(502, "YouTube verlangt eine Anmeldung für den Vercel-Server. Versuche spotDL lokal.")
                if "no results found" in diagnostic or "no matching" in diagnostic:
                    return self.reply(502, "spotDL hat für diesen Song keine passende YouTube-Aufnahme gefunden.")
                return self.reply(502, f"spotDL konnte keine MP3 erstellen. Details stehen in den Vercel-Logs unter {track_id}.")
            file = files[0]
            size = file.stat().st_size
            if not size:
                return self.reply(502, "Die MP3-Datei ist leer.")
            if size > MAX_MP3_BYTES:
                return self.reply(413, "Die MP3 ist zu groß für den Download über Vercel.")
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Disposition", f'attachment; filename="{track_id}.mp3"')
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(file.read_bytes())
