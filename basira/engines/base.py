"""Engine base class and registry.

Every AI engine is independent of the UI: it exposes load/unload/status and
a process API, so the same engines can later be reused by mobile/web apps.
Lazy loading keeps startup fast and memory low.
"""
from __future__ import annotations

import abc
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EngineState(str, Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"
    UNAVAILABLE = "unavailable"  # model or hardware missing on this machine


@dataclass
class EngineStatus:
    name: str
    state: EngineState
    detail: str = ""
    last_latency_ms: float | None = None


class BaseEngine(abc.ABC):
    name: str = "engine"

    def __init__(self) -> None:
        self._state = EngineState.UNLOADED
        self._detail = ""
        self._lock = threading.RLock()
        self._last_latency: float | None = None

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def detail(self) -> str:
        return self._detail

    def status(self) -> EngineStatus:
        return EngineStatus(self.name, self._state, self._detail, self._last_latency)

    def load(self) -> None:
        with self._lock:
            if self._state == EngineState.READY:
                return
            try:
                self._state = EngineState.LOADING
                self._do_load()
                self._state = EngineState.READY
            except Exception as e:
                self._state = EngineState.ERROR
                self._detail = str(e)
                raise

    def unload(self) -> None:
        with self._lock:
            self._do_unload()
            self._state = EngineState.UNLOADED

    def _timed(self, fn, *args, **kwargs) -> Any:
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        self._last_latency = (time.perf_counter() - t0) * 1000.0
        return result

    @abc.abstractmethod
    def _do_load(self) -> None: ...

    def _do_unload(self) -> None: ...


class EngineRegistry:
    def __init__(self) -> None:
        self._engines: dict[str, BaseEngine] = {}
        self._lock = threading.Lock()

    def register(self, engine: BaseEngine) -> None:
        with self._lock:
            self._engines[engine.name] = engine

    def get(self, name: str) -> BaseEngine:
        return self._engines[name]

    def all_status(self) -> list[EngineStatus]:
        return [e.status() for e in self._engines.values()]

    def shutdown(self) -> None:
        for e in self._engines.values():
            try:
                e.unload()
            except Exception:
                pass
