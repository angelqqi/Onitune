"""Historial de descargas terminadas, guardado en history.json."""

import os
import threading
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from typing import Callable

from . import paths


@dataclass
class HistoryEntry:
    title: str
    url: str
    kind: str  # "audio" o "video"
    options: dict  # las opciones usadas, para poder volver a descargar
    label: str  # texto corto: "MP3 · Mejor calidad"
    filepath: str = ""
    size: int = 0
    date: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    @property
    def when(self) -> datetime:
        try:
            return datetime.fromisoformat(self.date)
        except ValueError:
            return datetime.now()

    @property
    def file_exists(self) -> bool:
        return bool(self.filepath) and os.path.exists(self.filepath)


class History:
    def __init__(self):
        self._file = paths.data_dir() / "history.json"
        self._lock = threading.Lock()
        self.entries: list[HistoryEntry] = []
        self.listeners: list[Callable[[], None]] = []
        self._load()

    def _load(self) -> None:
        known = {f.name for f in fields(HistoryEntry)}
        for d in paths.read_json(self._file, []):
            try:
                self.entries.append(HistoryEntry(**{k: v for k, v in d.items() if k in known}))
            except (TypeError, AttributeError):
                continue  # una entrada dañada no borra las demás

    def _save(self) -> None:
        try:
            paths.write_json(self._file, [asdict(e) for e in self.entries])
        except OSError:
            pass  # disco lleno o sin permiso: se intenta de nuevo en el próximo cambio

    def _changed(self) -> None:
        for listener in list(self.listeners):
            listener()

    def add(self, entry: HistoryEntry) -> None:
        with self._lock:
            self.entries.insert(0, entry)  # lo más nuevo primero
            self._save()
        self._changed()

    def delete(self, entry_id: str, delete_file: bool = False) -> None:
        with self._lock:
            for entry in self.entries:
                if entry.id == entry_id:
                    if delete_file and entry.file_exists:
                        try:
                            os.remove(entry.filepath)
                        except OSError:
                            pass
                    self.entries.remove(entry)
                    break
            self._save()
        self._changed()

    def clear(self, delete_files: bool = False) -> int:
        """Borra todo el historial de una vez. Devuelve cuántas entradas había."""
        with self._lock:
            count = len(self.entries)
            if delete_files:
                for entry in self.entries:
                    if entry.file_exists:
                        try:
                            os.remove(entry.filepath)
                        except OSError:
                            pass  # archivo en uso o sin permiso: se deja
            self.entries = []
            self._save()
        self._changed()
        return count
