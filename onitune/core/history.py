"""Historial de descargas terminadas, guardado en history.json."""

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
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
        if not self._file.exists():
            return
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            known = HistoryEntry.__dataclass_fields__.keys()
            self.entries = [HistoryEntry(**{k: v for k, v in d.items() if k in known}) for d in data]
        except (OSError, ValueError, TypeError):
            self.entries = []

    def _save(self) -> None:
        data = [asdict(e) for e in self.entries]
        self._file.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

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
