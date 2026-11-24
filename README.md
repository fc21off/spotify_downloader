# MP3 für die Platte

## Vercel

1. Entpacke das ZIP und lade seinen Inhalt in das Hauptverzeichnis eines neuen GitHub-Repos.
2. Importiere das Repo in Vercel. Lege unter Environment Variables DOWNLOAD_PASSWORD fest. Nutze ein langes, zufälliges Passwort aus ASCII-Zeichen und teile es privat.
3. Klicke auf Deploy. Öffne die Vercel-URL und gib einen Spotify-Link zu einem einzelnen Song und das App-Passwort ein.

spotDL bezieht das Audio über YouTube und liefert MP3 mit 128 kbit/s. Vergleiche die heruntergeladene Aufnahme mit der gewünschten Fassung. Die App gibt Dateien bis 4,4 MB aus.

## Falls YouTube Vercel blockiert

Führe spotDL lokal aus. Ersetze den Platzhalter durch den gewünschten Spotify-Link.

    py -m pip install spotdl
    py -m spotdl --download-ffmpeg
    py -m spotdl download "https://open.spotify.com/track/DEINE_TRACK_ID"

Wenn yt-dlp eine JavaScript-Laufzeit verlangt, installiere Deno über spotDL mit py -m spotdl --download-deno und wiederhole den Download.
