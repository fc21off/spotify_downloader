import base64
import binascii
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


def votify_failure(details):
    message = details.lower()
    if "audio key" in message or "decrypt" in message:
        return "Spotify hat den Audiostream für diese Sitzung nicht freigegeben."
    if "401" in message or "403" in message or "login" in message or "sp_dc" in message:
        return "Spotify hat die Sitzung abgelehnt. Prüfe die in Vercel gespeicherten Spotify-Cookies."
    if "429" in message:
        return "Spotify begrenzt gerade die Anfragen. Versuche es später erneut."
    return "Votify hat keine Audiodatei für diesen Track geliefert."


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

        encoded_cookies = os.environ.get("SPOTIFY_COOKIES_B64", "").strip()
        if not encoded_cookies:
            return self.reply(503, "Setze SPOTIFY_COOKIES_B64 als Secret im Vercel-Projekt.")
        try:
            cookies = base64.b64decode(encoded_cookies, validate=True)
        except (binascii.Error, ValueError):
            return self.reply(503, "SPOTIFY_COOKIES_B64 muss die Cookies-Datei als Base64 enthalten.")
        if b"\tsp_dc\t" not in cookies:
            return self.reply(503, "Der Spotify-Cookie-Export enthält keinen sp_dc-Sitzungscookie.")

        track_id = match.group(1)
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            cookie_file = workspace / "spotify-cookies.txt"
            cookie_file.write_bytes(cookies)
            output = workspace / "audio"
            env = {
                **os.environ,
                "HOME": directory,
                "XDG_CACHE_HOME": directory,
                "PYTHONPATH": os.pathsep.join(path for path in sys.path if os.path.isabs(path)),
                "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
            }
            env.pop("DOWNLOAD_PASSWORD", None)
            env.pop("SPOTIFY_COOKIES_B64", None)
            try:
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                result = subprocess.run(
                    [
                        sys.executable, "-m", "votify", "--no-config-file",
                        "--cookies-path", str(cookie_file), "--session-type", "librespot",
                        "--audio-quality", "vorbis-medium", "--output", str(output),
                        "--temp", directory, "--wait-interval", "0",
                        "--no-synced-lyrics-file", "--ffmpeg-path", ffmpeg,
                        "https://open.spotify.com/track/" + track_id,
                    ],
                    cwd=directory, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                    timeout=85, text=True, encoding="utf-8", errors="replace",
                )
            except subprocess.TimeoutExpired:
                return self.reply(504, "Votify hat für den Spotify-Abruf zu lange gebraucht.")
            except (OSError, RuntimeError):
                print(f"Votify or FFmpeg could not start for {track_id}", file=sys.stderr, flush=True)
                return self.reply(502, "Votify oder FFmpeg konnte nicht gestartet werden.")

            files = list(output.rglob("*.ogg"))
            if result.returncode or len(files) != 1:
                message = votify_failure(result.stdout + "\n" + result.stderr)
                print(
                    f"Votify failed for {track_id} (exit {result.returncode}): {message}",
                    file=sys.stderr, flush=True,
                )
                return self.reply(502, message)

            mp3 = workspace / "audio.mp3"
            try:
                subprocess.run(
                    [
                        ffmpeg, "-nostdin", "-v", "error", "-i", str(files[0]),
                        "-map", "0:a:0", "-map_metadata", "0:s:a:0",
                        "-c:a", "libmp3lame", "-b:a", "128k", str(mp3),
                    ],
                    cwd=directory, env=env, capture_output=True, timeout=25, check=True,
                )
            except (subprocess.SubprocessError, OSError):
                return self.reply(502, "FFmpeg konnte den Spotify-Stream nicht als MP3 speichern.")

            size = mp3.stat().st_size
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
            self.wfile.write(mp3.read_bytes())
