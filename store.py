"""해결, 복구 때 고칠 카드의 메시지 ID 저장소"""
from __future__ import annotations

import json
import os
import threading

LIMIT = 500


class Store:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def add(self, key: str, entry: dict) -> None:
        with self._lock:
            data = self._load()
            # 다시 넣은 키를 맨 뒤로 보내 오래된 키부터 지운다
            entries = (data.pop(key, None) or [])[-4:] + [entry]
            data[key] = entries
            for old in list(data)[:-LIMIT]:
                del data[old]
            self._save(data)

    def pop(self, key: str) -> list:
        with self._lock:
            data = self._load()
            entries = data.pop(key, None) or []
            if entries:
                self._save(data)
            return entries
