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
from .settings import Settings

YOUTUBE_URL = re.compile(r"https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/\S+", re.IGNORECASE)


LIVE_ERROR = "Es una transmisión en vivo: no se puede descargar mientras está al aire"


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


def is_url(text: str) -> bool:
    return bool(re.match(r"^https?://", text.strip(), re.IGNORECASE))


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
            return f"{text.replace('.', ',')} {unit}"
        size /= 1024
    return ""


def safe_folder_name(name: str) -> str:
    """Quita los caracteres que Windows no permite en nombres de carpeta."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .")
    return cleaned[:100] or "Playlist"


def friendly_error(text: str) -> str:
    """Traduce los errores más comunes de yt-dlp a algo entendible."""
    lower = text.lower()
    if "confirm your age" in lower or "age-restricted" in lower or "inappropriate" in lower:
        return "Video con restricción de edad: requiere cookies (ver Ajustes)"
    if "sign in to confirm you" in lower and "bot" in lower:
        return "YouTube pide iniciar sesión: requiere cookies (ver Ajustes)"
    if "private video" in lower:
        return "Video privado: requiere cookies de una cuenta con acceso (ver Ajustes)"
    if "members-only" in lower or "join this channel" in lower:
        return "Video solo para miembros: requiere cookies (ver Ajustes)"
    if "video unavailable" in lower or "not available" in lower:
        return "El video no está disponible"
    if "unable to download webpage" in lower or "getaddrinfo" in lower or "timed out" in lower:
        return "Sin conexión a internet o YouTube no responde"
    if "ffmpeg" in lower and "not found" in lower:
        return "Falta ffmpeg: se instala al volver a abrir la app"
    if "unsupported url" in lower:
        return "Ese enlace no es compatible"
    text = text.strip()
    if text.startswith("ERROR:"):
        text = text[6:].strip()
    return text[:200] or "Error desconocido"


def _last_error(output: str) -> str:
    errors = [line for line in output.splitlines() if line.startswith("ERROR:")]
    return errors[-1] if errors else (output.strip().splitlines() or [""])[-1]


def cookie_args(settings: Settings) -> list[str]:
    if settings.cookies_mode == "browser" and settings.cookies_browser:
        return ["--cookies-from-browser", settings.cookies_browser]
    if settings.cookies_mode == "file" and settings.cookies_file:
        return ["--cookies", settings.cookies_file]
    return []


def _base_args(settings: Settings) -> list[str]:
    args = [str(paths.ytdlp_path()), "--encoding", "utf-8", "--no-warnings"]
    location = deps.ffmpeg_location()
    if location:
        args += ["--ffmpeg-location", location]
    return args + cookie_args(settings)


def _run_json(args: list[str], timeout: float) -> dict:
    try:
        result = proc.run(args, timeout=timeout)
    except Exception as exc:  # timeout, programa no encontrado...
        raise YtdlpError(f"No se pudo ejecutar yt-dlp: {exc}") from exc
    if result.returncode != 0 or not result.stdout.strip():
        raise YtdlpError(friendly_error(_last_error(result.stderr or result.stdout)))
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise YtdlpError("yt-dlp devolvió una respuesta que no se entiende") from exc


def _thumb(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


# ---------------------------------------------------------------- búsqueda y análisis


def search(query: str, settings: Settings, limit: int = 10) -> list[SearchResult]:
    if settings.music_search:
        return search_music(query, settings, limit)
    data = _run_json(_base_args(settings) + ["--flat-playlist", "-J", f"ytsearch{limit}:{query}"], timeout=90)
    results = []
    for e in data.get("entries") or []:
        if not e or not e.get("id"):
            continue
        results.append(
            SearchResult(
                id=e["id"],
                title=e.get("title") or "(sin título)",
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
    args = _base_args(settings) + ["--skip-download", "--playlist-end", str(limit), "--print", fields, url]
    try:
        result = proc.run(args, timeout=120)
    except Exception as exc:
        raise YtdlpError(f"No se pudo ejecutar yt-dlp: {exc}") from exc

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
                title=e.get("title") or "(sin título)",
                channel=" · ".join(x for x in (artist, album) if x),
                duration=fmt_duration(e.get("duration")),
                url=f"https://www.youtube.com/watch?v={e['id']}",
                thumbnail=_thumb(e["id"]),
                live=e.get("live_status") == "is_live",
                music=True,
            )
        )
    if not results and result.returncode != 0:
        raise YtdlpError(friendly_error(_last_error(result.stderr or result.stdout)))
    return results


def probe(url: str, settings: Settings):
    """Mira rápido un enlace. Devuelve ("playlist", PlaylistInfo) o ("video", título)."""
    data = _run_json(_base_args(settings) + ["--flat-playlist", "-J", url], timeout=120)
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
                    title=e.get("title") or "(sin título)",
                    duration=fmt_duration(e.get("duration")),
                    url=f"https://www.youtube.com/watch?v={e['id']}",
                )
            )
        return "playlist", PlaylistInfo(title=data.get("title") or "Playlist", entries=entries)
    if data.get("is_live"):
        raise YtdlpError(LIVE_ERROR)
    return "video", data.get("title") or url


SUB_NAMES = {
    "es": "Español", "en": "Inglés", "pt": "Portugués", "fr": "Francés", "de": "Alemán",
    "it": "Italiano", "ja": "Japonés", "ko": "Coreano", "zh": "Chino", "ru": "Ruso",
}


def _sub_label(code: str, tracks: list) -> str:
    base = code.split("-")[0]
    if base in SUB_NAMES:
        return SUB_NAMES[base]
    for t in tracks or []:
        if t.get("name"):
            return t["name"]
    return code


def analyze_video(url: str, settings: Settings) -> VideoInfo:
    """Lee todos los formatos reales de un video."""
    data = _run_json(_base_args(settings) + ["--no-playlist", "-J", url], timeout=120)
    if data.get("is_live"):
        raise YtdlpError(LIVE_ERROR)

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
            label = _sub_label(code, tracks) + " (automáticos)"
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
        quality = "Mejor calidad" if options["quality"] == "best" else f"{options['quality']} kbps"
        return f"{fmt} · {quality}"
    res = options.get("res")
    text = f"{options['container'].upper()} · {f'{res}p' if res else 'Mejor'}"
    if options.get("subs") and options.get("sub_lang"):
        text += f" · Subt. {options['sub_lang'].split('-')[0].upper()}"
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
    args = _base_args(settings) + [
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

    return args + [url]


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
