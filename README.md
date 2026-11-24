# MP3 für die Platte

Votify ruft einen einzelnen Track über eine angemeldete Spotify-Sitzung ab. Die Python-Funktion wandelt den Vorbis-Stream mit FFmpeg in eine MP3 mit 128 kbit/s um. Die Downloadgrenze liegt bei 4,4 MB.

## Vercel einrichten

1. Importiere dieses GitHub-Repo in Vercel oder verwende das bereits verbundene Projekt.
2. Behalte unter **Settings → Environment Variables** das vorhandene Secret **DOWNLOAD_PASSWORD** oder setze ein eigenes, zufälliges App-Passwort.
3. Exportiere die Cookies deiner eigenen angemeldeten Spotify-Sitzung im Netscape-Format wie in der [Votify-Dokumentation](https://github.com/glomatico/votify#-prerequisites) beschrieben. Der Export muss den Session-Cookie **sp_dc** enthalten.
4. Führe in PowerShell im Ordner der Datei den folgenden Befehl aus. Er kopiert die Base64-kodierte Datei direkt in die Zwischenablage.

   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path -LiteralPath '.\cookies.txt').Path)) | Set-Clipboard
   ```

5. Füge den Wert in Vercel als **Secret** mit dem Namen **SPOTIFY_COOKIES_B64** für **Production** ein. Der Export und sein Base64-Wert sind Zugangsdaten. Bewahre sie privat auf und lade sie nie ins Repo.
6. Deploye **main** erneut. Gib auf der App-Seite den Spotify-Link und das App-Passwort ein.

## Wenn der Abruf scheitert

- Meldet die App eine abgelehnte Sitzung, prüfe, ob der Cookie-Export frisch ist und ob die Variable für das aktuelle Deployment gesetzt wurde.
- Für den headless Linux-Betrieb nutzt die App den **librespot**-Modus. Spotify gibt den Audiozugriff nicht für jede Sitzung frei. [Kontokompatibilität bei librespot](https://github.com/librespot-org/librespot/issues/1649)
- Votify 1.9.9 ist archiviert. Das Projekt dokumentiert Berichte über gesperrte Spotify-Konten. [Votify-Voraussetzungen](https://github.com/glomatico/votify#-prerequisites)
