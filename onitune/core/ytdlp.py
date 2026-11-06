"""Todo lo que habla con yt-dlp: buscar, analizar enlaces y preparar descargas.

La app usa el programa yt-dlp (no la librería de Python). Así basta con
`yt-dlp -U` para arreglar la app cuando YouTube cambia algo.
"""

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

from . import deps, paths, proc
from .i18n import t
from .settings import Settings

YOUTUBE_URL = re.compile(r"https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/\S+", re.IGNORECASE)


class YtdlpError(Exception):
    """Error de yt-dlp con un mensaje que el usuario puede entender."""


# ---------------------------------------------------------------- datos


@dataclass
class SearchResult:
    id: str
    title: str
    channel: str
    duration: str
    url: str
    thumbnail: str
    live: bool = False
    music: bool = False  # viene de la búsqueda de YouTube Music


@dataclass
class PlaylistEntry:
    id: str
    title: str
    duration: str
    url: str


@dataclass
class PlaylistInfo:
    title: str
    entries: list[PlaylistEntry]


@dataclass
class Resolution:
    res: int  # lado más corto del video (1080, 720...)
    label: str
    detail: str


@dataclass
class SubtitleOption:
    code: str
    label: str
    auto: bool


@dataclass
class VideoInfo:
    id: str
    title: str
    channel: str
    duration: str
    url: str
    thumbnail: str
    resolutions: list[Resolution] = field(default_factory=list)
    subtitles: list[SubtitleOption] = field(default_factory=list)
    music: bool = False  # el enlace era de music.youtube.com


# ---------------------------------------------------------------- utilidades


def is_url(text) -> bool:
    """True si es un enlace web (http:// o https://, sin espacios).

    Python lo revisa aunque la página ya lo haga: así nunca le llega a yt-dlp
    un texto que empiece con "-", que leería como una opción (p. ej. --exec).
    """
    return isinstance(text, str) and bool(re.match(r"^https?://\S+$", text.strip(), re.IGNORECASE))


def is_youtube_url(text: str) -> bool:
    return bool(YOUTUBE_URL.match(text.strip()))


def is_playlist_url(url: str) -> bool:
    return "list=" in url


def is_music_url(url: str) -> bool:
    """True si el enlace es de YouTube Music (music.youtube.com)."""
    return "music.youtube.com" in url.lower()


def fmt_duration(seconds) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_size(size) -> str:
    if not size:
        return ""
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            text = f"{size:.0f}" if unit in ("B", "KB") or size >= 100 else f"{size:.1f}"
            return f"{text.replace('.', t('_decimal', default='.'))} {unit}"
        size /= 1024
    return ""


WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_folder_name(name: str) -> str:
    """Quita los caracteres que Windows no permite en nombres de carpeta."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .")[:100].strip(" .")
    # Windows tampoco deja usar estos nombres, aunque lleven algo después de un punto ("con.mp3")
    if cleaned.split(".")[0].strip().upper() in WINDOWS_RESERVED:
        cleaned = "_" + cleaned
    return cleaned or "Playlist"


def friendly_error(text: str) -> str:
    """Traduce los errores más comunes de yt-dlp a algo entendible."""
    lower = text.lower()
    # Cookies del navegador (van primero: el texto de estos errores es muy técnico)
    if "dpapi" in lower or "app-bound" in lower:
        return t("error.cookies_blocked")  # Chrome/Edge en Windows
    if "could not copy" in lower and "cookie" in lower:
        return t("error.cookies_locked")  # el navegador abierto bloquea el archivo
    if "could not find" in lower and "cookie" in lower:
        return t("error.cookies_not_found")
    if "netscape" in lower or ("cookies" in lower and "no such file" in lower):
        return t("error.cookies_bad_file")
    if "cookies are no longer valid" in lower:
        return t("error.cookies_expired")
    if "confirm your age" in lower or "age-restricted" in lower or "inappropriate" in lower:
        return t("error.age")
    if "sign in to confirm you" in lower and "bot" in lower:
        return t("error.bot")
    if "private video" in lower:
        return t("error.private")
    if "members-only" in lower or "join this channel" in lower:
        return t("error.members")
    if "video unavailable" in lower or "not available" in lower:
        return t("error.unavailable")
    if "unable to download webpage" in lower or "getaddrinfo" in lower or "timed out" in lower:
        return t("error.offline")
    if "ffmpeg" in lower and "not found" in lower:
        return t("error.no_ffmpeg")
    if "unsupported url" in lower:
        return t("error.unsupported")
    text = text.strip()
    if text.startswith("ERROR:"):
        text = text[6:].strip()
    return text[:200] or t("error.unknown")


def last_error(output: str) -> str:
    errors = [line for line in output.splitlines() if line.startswith("ERROR:")]
    return errors[-1] if errors else (output.strip().splitlines() or [""])[-1]


def cookie_args(settings: Settings) -> list[str]:
    if settings.cookies_mode == "browser" and settings.cookies_browser:
        return ["--cookies-from-browser", settings.cookies_browser]
    if settings.cookies_mode == "file" and settings.cookies_file:
        return ["--cookies", settings.cookies_file]
    return []


def base_args(settings: Settings) -> list[str]:
    # --ignore-config: no leer archivos de configuración de yt-dlp (el del usuario
    # o un yt-dlp.conf en la carpeta de descargas). Podrían cambiar las descargas
    # o hasta ejecutar programas (--exec).
    args = [str(paths.ytdlp_path()), "--ignore-config", "--encoding", "utf-8", "--no-warnings"]
    location = deps.ffmpeg_location()
    if location:
        args += ["--ffmpeg-location", location]
    return args + deps.js_runtime_args() + cookie_args(settings)


def _run_json(args: list[str], timeout: float) -> dict:
    try:
        result = proc.run(args, timeout=timeout)
    except Exception as exc:  # timeout, programa no encontrado...
        raise YtdlpError(t("error.run", error=exc)) from exc
    if result.returncode != 0 or not result.stdout.strip():
        raise YtdlpError(friendly_error(last_error(result.stderr or result.stdout)))
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise YtdlpError(t("error.bad_answer")) from exc


def _thumb(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


# ---------------------------------------------------------------- búsqueda y análisis


def search(query: str, settings: Settings, limit: int = 10) -> list[SearchResult]:
    if settings.music_search:
        return search_music(query, settings, limit)
    data = _run_json(base_args(settings) + ["--flat-playlist", "-J", "--", f"ytsearch{limit}:{query}"], timeout=90)
    results = []
    for e in data.get("entries") or []:
        if not e or not e.get("id"):
            continue
        results.append(
            SearchResult(
                id=e["id"],
                title=e.get("title") or t("ytdlp.no_title"),
                channel=e.get("channel") or e.get("uploader") or "",
                duration=fmt_duration(e.get("duration")),
                url=f"https://www.youtube.com/watch?v={e['id']}",
                thumbnail=_thumb(e["id"]),
                live=e.get("live_status") == "is_live",
            )
        )
    return results


def search_music(query: str, settings: Settings, limit: int = 10) -> list[SearchResult]:
    """Busca solo canciones en YouTube Music.

    Las canciones de YouTube Music traen artista y álbum bien puestos, así el
    archivo descargado queda con mejores metadatos. Tarda un poco más que la
    búsqueda normal porque yt-dlp abre cada canción para leer esos datos.
    """
    url = "https://music.youtube.com/search?" + urllib.parse.urlencode({"q": query}) + "#songs"
    # yt-dlp imprime una línea JSON por canción con solo los campos que pedimos
    fields = "%(.{id,title,artists,album,duration,channel,live_status})j"
    args = base_args(settings) + ["--skip-download", "--playlist-end", str(limit), "--print", fields, "--", url]
    try:
        result = proc.run(args, timeout=120)
    except Exception as exc:
        raise YtdlpError(t("error.run", error=exc)) from exc

    results = []
    for line in result.stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue  # no es una línea de datos
        if not e.get("id"):
            continue
        # Lo que se ve debajo del título: "Artista · Álbum"
        artist = (e.get("artists") or [e.get("channel") or ""])[0]
        album = e.get("album") or ""
        results.append(
            SearchResult(
                id=e["id"],
                title=e.get("title") or t("ytdlp.no_title"),
                channel=" · ".join(x for x in (artist, album) if x),
                duration=fmt_duration(e.get("duration")),
                url=f"https://www.youtube.com/watch?v={e['id']}",
                thumbnail=_thumb(e["id"]),
                live=e.get("live_status") == "is_live",
                music=True,
            )
        )
    if not results and result.returncode != 0:
        raise YtdlpError(friendly_error(last_error(result.stderr or result.stdout)))
    return results


def probe(url: str, settings: Settings):
    """Mira rápido un enlace. Devuelve ("playlist", PlaylistInfo) o ("video", datos para la vista previa)."""
    data = _run_json(base_args(settings) + ["--flat-playlist", "-J", "--", url], timeout=120)
    if data.get("_type") == "playlist":
        entries = []
        for e in data.get("entries") or []:
            if not e or not e.get("id"):
                continue
            if e.get("live_status") == "is_live":
                continue
            entries.append(
                PlaylistEntry(
                    id=e["id"],
                    title=e.get("title") or t("ytdlp.no_title"),
                    duration=fmt_duration(e.get("duration")),
                    url=f"https://www.youtube.com/watch?v={e['id']}",
                )
            )
        return "playlist", PlaylistInfo(title=data.get("title") or "Playlist", entries=entries)
    if data.get("is_live"):
        raise YtdlpError(t("error.live"))
    # Lo que se ve debajo del título: "Artista · Álbum" (canciones) o el canal
    artist = (data.get("artists") or [data.get("channel") or data.get("uploader") or ""])[0]
    return "video", {
        "title": data.get("title") or url,
        "channel": " · ".join(x for x in (artist, data.get("album") or "") if x),
        "duration": fmt_duration(data.get("duration")),
        "thumbnail": data.get("thumbnail") or (_thumb(data["id"]) if data.get("id") else ""),
    }


def _sub_label(code: str, tracks: list) -> str:
    # Los idiomas más comunes con su nombre traducido ("lang.es"); el resto, con el nombre que da YouTube
    name = t("lang." + code.split("-")[0], default="")
    if name:
        return name
    for track in tracks or []:
        if track.get("name"):
            return track["name"]
    return code


def analyze_video(url: str, settings: Settings) -> VideoInfo:
    """Lee todos los formatos reales de un video."""
    data = _run_json(base_args(settings) + ["--no-playlist", "-J", "--", url], timeout=120)
    if data.get("is_live"):
        raise YtdlpError(t("error.live"))

    # Mejor audio (para sumar su tamaño a cada calidad de video)
    audio_size = 0
    for f in data.get("formats") or []:
        if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none"):
            audio_size = max(audio_size, f.get("filesize") or f.get("filesize_approx") or 0)

    # Agrupamos los formatos de video por resolución
    by_res: dict[int, dict] = {}
    for f in data.get("formats") or []:
        if f.get("vcodec") in (None, "none") or not f.get("height"):
            continue
        res = min(f["height"], f.get("width") or f["height"])
        if res < 144:
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        entry = by_res.setdefault(res, {"fps": 0, "size": 0, "tbr": -1})
        entry["fps"] = max(entry["fps"], f.get("fps") or 0)
        if (f.get("tbr") or 0) > entry["tbr"]:
            entry["tbr"] = f.get("tbr") or 0
            entry["size"] = size

    resolutions = []
    for res in sorted(by_res, reverse=True):
        info = by_res[res]
        names = {2160: "2160p 4K", 1440: "1440p 2K", 4320: "4320p 8K"}
        details = []
        if info["size"]:
            details.append("~" + fmt_size(info["size"] + audio_size))
        if info["fps"]:
            details.append(f"{int(info['fps'])} fps")
        resolutions.append(Resolution(res=res, label=names.get(res, f"{res}p"), detail=" · ".join(details)))

    # Subtítulos: los manuales y los automáticos más útiles
    subtitles = []
    for code, tracks in (data.get("subtitles") or {}).items():
        if code != "live_chat":
            subtitles.append(SubtitleOption(code, _sub_label(code, tracks), auto=False))
    auto = data.get("automatic_captions") or {}
    original = data.get("language") or ""
    for code, tracks in auto.items():
        if code.endswith("-orig") or code in ("es", "en") or (original and code == original):
            label = t("ytdlp.auto_subs", name=_sub_label(code, tracks))
            subtitles.append(SubtitleOption(code, label, auto=True))

    return VideoInfo(
        id=data.get("id") or "",
        title=data.get("title") or url,
        channel=data.get("channel") or data.get("uploader") or "",
        duration=fmt_duration(data.get("duration")),
        url=data.get("webpage_url") or url,
        thumbnail=data.get("thumbnail") or (_thumb(data["id"]) if data.get("id") else ""),
        resolutions=resolutions,
        subtitles=subtitles,
        music=is_music_url(url),
    )


# ---------------------------------------------------------------- descargas

PROGRESS_TAG = "[onitune-progress]"
TITLE_TAG = "[onitune-title]"
FILE_TAG = "[onitune-file]"


def describe_options(options: dict) -> str:
    """Texto corto para mostrar en la cola y el historial: "MP3 · Mejor calidad"."""
    if options["kind"] == "audio":
        fmt = options["format"].upper()
        if options["format"] in ("flac", "wav"):
            return fmt
        quality = t("ytdlp.best_quality") if options["quality"] == "best" else f"{options['quality']} kbps"
        return f"{fmt} · {quality}"
    res = options.get("res")
    text = f"{options['container'].upper()} · {f'{res}p' if res else t('ytdlp.best')}"
    if options.get("subs") and options.get("sub_lang"):
        text += " · " + t("ytdlp.subs", lang=options["sub_lang"].split("-")[0].upper())
    return text


# Recorte de la portada a un cuadrado del centro (como la muestra YouTube Music).
# YouTube guarda las miniaturas en 16:9 y rellena los lados de las portadas
# cuadradas. Lado del cuadrado = min(alto, ancho*9/16): así también se quitan
# las barras negras de las miniaturas 4:3 (hqdefault), que traen el 16:9 dentro.
# Las comillas dobles y simples hacen falta para que las comas lleguen a ffmpeg.
CROP_COVER_ARGS = [
    # yt-dlp no convierte una imagen que ya está en el formato pedido, y entonces
    # no recortaría: por eso las JPG pasan a PNG y el resto a JPG.
    "--convert-thumbnails", "jpg>png/jpg",
    "--ppa", "ThumbnailsConvertor+FFmpeg_o:-q:v 2 -vf crop=\"'min(ih,iw*9/16)':'min(ih,iw*9/16)'\"",
]


def crop_cover(options: dict, settings: Settings) -> bool:
    """¿Hay que recortar la portada de esta descarga? Depende del ajuste cover_crop."""
    mode = settings.cover_crop
    if mode == "both":
        return True
    if mode == "music":
        return bool(options.get("music"))
    return mode == options["kind"]  # "audio" o "video"


def download_args(url: str, options: dict, out_dir: str, tmp_dir: str, settings: Settings) -> list[str]:
    """Arma la línea de comandos de yt-dlp para una descarga."""
    args = base_args(settings) + [
        "--newline",
        "--progress",
        "--no-playlist",
        "--no-mtime",
        "--windows-filenames",
        "--trim-filenames", "150",
        "-P", f"home:{out_dir}",
        "-P", f"temp:{tmp_dir}",
        "-o", "%(title)s.%(ext)s",
        "--progress-template",
        "download:" + PROGRESS_TAG + " %(progress.status)s|%(progress.downloaded_bytes)s|"
        "%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|%(progress.eta)s",
        "--print", "before_dl:" + TITLE_TAG + " %(title)s",
        "--print", "after_move:" + FILE_TAG + " %(filepath)s",
    ]

    if options["kind"] == "audio":
        fmt = options["format"]
        if fmt == "m4a":
            args += ["-f", "bestaudio[ext=m4a]/bestaudio"]
        elif fmt == "opus":
            args += ["-f", "bestaudio[acodec=opus]/bestaudio"]
        else:
            args += ["-f", "bestaudio/best"]
        quality = "0" if options["quality"] == "best" else f"{options['quality']}K"
        args += ["-x", "--audio-format", fmt, "--audio-quality", quality]
        if options.get("metadata", True):
            args += ["--embed-metadata"]
        if options.get("cover", True) and fmt != "wav":
            args += ["--embed-thumbnail"]
            if crop_cover(options, settings):
                args += CROP_COVER_ARGS
        if fmt == "mp3":
            # ID3v2.3 hace que la portada se vea en Windows y en más reproductores
            args += ["--ppa", "ffmpeg:-id3v2_version 3"]
    else:
        res = options.get("res")
        container = options["container"]
        sort = f"res:{res}" if res else "res"
        if container == "mp4":
            sort += ",vcodec:h264,acodec:m4a"  # lo más compatible
        args += [
            "-f", "bv*+ba/b",
            "-S", sort,
            "--merge-output-format", container,
            "--remux-video", container,
            "--embed-metadata",
            "--embed-thumbnail",
        ]
        if crop_cover(options, settings):
            args += CROP_COVER_ARGS
        if options.get("subs") and options.get("sub_lang"):
            embed = options.get("subs_embed", True)
            if options.get("sub_auto"):
                args += ["--write-auto-subs"]
            elif not embed:
                # Ojo: si pasamos --write-subs junto a --embed-subs, yt-dlp deja
                # también el .srt suelto. Para incrustar basta con --embed-subs.
                args += ["--write-subs"]
            args += ["--sub-langs", options["sub_lang"], "--convert-subs", "srt"]
            if embed:
                args += ["--embed-subs"]

    # "--": desde aquí yt-dlp ya no busca opciones; el enlace nunca se lee como una opción
    return args + ["--", url]


def _num(text: str) -> Optional[float]:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def parse_progress(line: str) -> Optional[dict]:
    """Convierte una línea de progreso de yt-dlp en un diccionario."""
    if not line.startswith(PROGRESS_TAG):
        return None
    parts = line[len(PROGRESS_TAG):].strip().split("|")
    if len(parts) < 6:
        return None
    status, done, total, estimate, speed, eta = parts[:6]
    done_n = _num(done) or 0
    total_n = _num(total) or _num(estimate) or 0
    return {
        "status": status,
        "fraction": (done_n / total_n) if total_n else None,
        "downloaded": done_n,
        "total": total_n,
        "speed": _num(speed),
        "eta": _num(eta),
    }
