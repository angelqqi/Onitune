<p align="center"><img src="assets/icon.png" width="128" alt="Onitune icon: an onigiri shaped like a play button"></p>

<h1 align="center">Onitune</h1>

<p align="center">
  <b>A beautiful, simple and free app to download music and video from YouTube.</b><br>
  MP3 or FLAC with the right cover and artist · Video up to 4K · 14 color themes · No ads
</p>

<p align="center">
  <a href="https://github.com/angelqqi/Onitune/releases/latest"><img src="https://img.shields.io/github/v/release/angelqqi/Onitune?label=version&color=bd93f9" alt="Latest version"></a>
  <a href="https://github.com/angelqqi/Onitune/releases"><img src="https://img.shields.io/github/downloads/angelqqi/Onitune/total?label=downloads&color=ff79c6" alt="Downloads"></a>
  <img src="https://img.shields.io/badge/Windows%20%7C%20Linux-50fa7b?label=runs%20on" alt="Windows and Linux">
  <a href="LICENSE"><img src="https://img.shields.io/github/license/angelqqi/Onitune?label=license&color=8be9fd" alt="MIT license"></a>
</p>

<p align="center">
  <a href="https://github.com/angelqqi/Onitune/releases/latest"><b>⬇️ Download for Windows</b></a>
  &nbsp;·&nbsp; no Python needed · no admin rights<br>
  <a href="README.es.md">Leer en español</a>
</p>

<p align="center"><img src="docs/capturas/portada.png" alt="Onitune analyzing a video: it shows the available qualities, from 144p to 4K, in a dark and a light theme"></p>

## Features

- **Audio:** MP3, M4A, OPUS, FLAC or WAV, with cover art and tags. Paste a link or search by name.
- **YouTube Music search:** songs come out with the right artist and album. A square cover is cropped from the thumbnail, just like in YouTube Music.
- **Video:** shows only the qualities each video really has (up to 4K and 60 fps). MP4 or MKV, with subtitles.
- **Playlists:** pick which videos to download.
- **Downloads:** several at once; pause, resume, cancel or retry. They continue if you close the app.
- **History:** search, open the file or folder, download again or clear it all.
- **Languages:** English, Spanish and Portuguese. English by default; change it in Settings (or pick "Automatic" to follow the system language).
- **Extras:** 14 themes (Dracula, Tokyo Night, Catppuccin, Nord, Gruvbox, Rosé Pine…), notices when you copy a YouTube link, browser cookies for age-restricted videos and update alerts.

<details>
<summary><b>📸 Screenshots</b></summary>
<br>

| Search music by name | Pick the video quality |
|---|---|
| <img src="docs/capturas/audio.png" alt="Audio tab: search results and formats"> | <img src="docs/capturas/video.png" alt="Video tab: qualities from 144p to 4K"> |
| **Several downloads at once** | **History** |
| <img src="docs/capturas/descargas.png" alt="Downloads tab with progress bars"> | <img src="docs/capturas/historial.png" alt="History tab with filters"> |
| **Settings** | **Copied link notice** |
| <img src="docs/capturas/ajustes.png" alt="Settings tab: folders, cookies and themes"> | <img src="docs/capturas/portapapeles.png" alt="Notice for a copied YouTube link"> |

**14 color themes**

<img src="docs/capturas/temas.png" alt="The same screen in 9 of the 14 themes">

Screenshots use freely licensed content: open movies by [Blender](https://studio.blender.org/films/) and music by [NoCopyrightSounds](https://ncs.io).

</details>

## Download

Get it from the [latest release](https://github.com/angelqqi/Onitune/releases/latest). None of these need Python or admin rights:

| File | What it is |
|---|---|
| `Onitune-Setup-X.Y.Z.exe` | **Installer** (recommended): adds Onitune to the Start menu and uninstalls from Windows settings. |
| `Onitune-X.Y.Z-windows.zip` | **Portable**: unzip the folder and open `Onitune.exe`. Opens the fastest. |
| `Onitune.exe` | **Single file**: runs without installing, but opens a bit slower. |

On first launch, Onitune downloads **yt-dlp** and **ffmpeg** from their official sites by itself.

**Linux (Debian, Ubuntu, Mint...):** download `onitune_X.Y.Z_all.deb` and install it with `sudo apt install ./onitune_X.Y.Z_all.deb` (apt adds what it needs). Then open Onitune from the app menu or by typing `onitune`. On other distros, run it with Python (see below).

### "Windows protected your PC"?

Windows shows this warning for apps that are not digitally signed, which is common for small free projects. To open Onitune, click **More info → Run anyway**.

Some antivirus programs also flag apps built with PyInstaller by mistake. Onitune is open source, so you can:
- check the file with the SHA256 hashes in `SHA256SUMS.txt` (also in each release's notes),
- read the code or build it yourself (see below),
- and if your antivirus flags it, please [open an issue](https://github.com/angelqqi/Onitune/issues) so it can be reported as a false positive.

## Run with Python

| | Windows | Linux |
|---|---|---|
| With Python 3.13 | Double-click `Onitune.bat` | `./Onitune.sh` |

The launchers update the code (`git pull`), create a `.venv` the first time, install `requirements.txt` and open the app.

The window uses the system's browser engine: on Windows, Edge WebView2 (already included in Windows 10 and 11). On Linux it needs GTK and WebKit; on Ubuntu/Debian: `sudo apt install python3-venv python3-gi gir1.2-webkit2-4.1`. Tested on Ubuntu 26.04 with its own Python 3.14.

<details>
<summary><b>🌍 Add a language</b></summary>
<br>

Adding a language only takes translating one file, no code needed:

1. Copy `onitune/idiomas/en.json` and name it with the language code, for example `fr.json`.
2. Translate the texts on the right. Leave as they are: the keys on the left, the words in braces (`{n}`, `{text}`…) and the `"one"` / `"other"` names (singular and plural).
3. Set `_name` to the language's own name (`Français`) and `_decimal` to its decimal separator.
4. Open the app, pick the language in **Settings → Language** and check how it looks. Any missing text shows up in Spanish.

Then send it as a pull request, or attach the file to an [issue](https://github.com/angelqqi/Onitune/issues).

</details>

<details>
<summary><b>For developers</b>: build, data folders and code layout</summary>

### Build the executable

```bash
.venv\Scripts\python -m pip install -r requirements-build.txt   # Windows
winget install JRSoftware.InnoSetup                              # only for the installer
python build.py
```

Everything ends up in `dist/`: the installer, the portable `.zip`, the single `.exe` and `SHA256SUMS.txt`. yt-dlp is **not** bundled on purpose: it updates itself, so there's no need to rebuild every time YouTube changes something.

### Where it saves things

| What | Windows | Linux |
|---|---|---|
| Settings, pending downloads, history, yt-dlp and ffmpeg | `%LOCALAPPDATA%\Onitune` | `~/.local/share/onitune` |
| Downloaded files (default, can be changed in Settings) | `Music\Onitune\Audio` and `Videos\Onitune\Video` | `~/Music/Onitune/...` and `~/Videos/Onitune/...` |

### Code layout

```
main.py                 Entry point: opens the window
onitune/
  core/                 The logic, no interface code
    paths.py            Where each thing is saved
    settings.py         Settings (settings.json)
    deps.py             Downloads and updates yt-dlp and ffmpeg
    ytdlp.py            Talks to yt-dlp: search, analyze and build the download command
    queue.py            Download queue: runs yt-dlp, reads progress, pauses and cancels
    history.py          History (history.json)
    updates.py          Checks GitHub for a new Onitune version
    notify.py           System notifications
    proc.py             Runs programs without console windows, opens files and folders
    clipboard.py        Reads the clipboard (Windows and Linux)
    i18n.py             Loads the texts of the chosen language
  idiomas/              One file per language: es.json, en.json, pt.json
  ui/                   The interface: a web page shown with pywebview
    app.py              Opens the window and sends changes to the page (queue, history, notices)
    api.py              Python functions the page can call (search, analyze, download...)
    themes.py           Color themes (to add one, add it to the list)
    web/                The page: index.html, style.css and app.js
tools/make_icon.py      Draws the icon (assets/icon.png, assets/icon.ico)
build.py                Builds the executable
```

`core/` knows nothing about the interface, and `ui/` never talks to yt-dlp directly. If YouTube changes something, updating yt-dlp (button in Settings) is usually enough. Searches and downloads run in background threads; `ui/app.py` groups their changes and sends them to the page in batches.

Code comments are in Spanish.

</details>

## Credits

- **Idea, design and direction:** [angelqqi](https://github.com/angelqqi).
- **Code:** written with the help of AI ([Claude](https://claude.com), by Anthropic), following angelqqi's directions and decisions.

<details>
<summary>A note from the author</summary>
<br>

I built Onitune in my free time, out of curiosity: I wanted to see what AI is capable of. I'm not a software developer and my programming knowledge is still basic; without that help I couldn't have made this app on my own. If any programmer finds some blasphemy in the code, I apologize in advance.

I don't plan to leave the project behind. Work doesn't let me dedicate myself to it full time, but I keep learning little by little and adding features with Claude's help. Any feedback or advice is welcome. I hope you find it useful.

</details>

## License and legal notice

- Onitune's code is under the **MIT** license (see [LICENSE](LICENSE)). Third-party programs it uses (yt-dlp, FFmpeg, pywebview…) and their licenses are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). yt-dlp and FFmpeg are **not** bundled: the app downloads them from their official sites.
- Onitune is **not affiliated** with YouTube or Google. "YouTube" is a trademark of Google LLC and is only mentioned to describe what the app does.
- Downloading content may go against YouTube's terms or the creator's copyright. **Only use the app with content you have the right to save** (for example, your own videos or freely licensed content). Each person is responsible for how they use it.
