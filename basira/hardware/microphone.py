"""Microphone capture and audio output playback.

Uses python-sounddevice (PortAudio) when present. On systems without
PortAudio (or without any input device) every method raises
HardwareUnavailableError instead of crashing, and the DeviceManager reports
the device as unavailable. Tests exercise the pure-Python parts (WAV
encoding, level metering, RMS/VAD gating) without any audio hardware.
"""
from __future__ import annotations

import io
import queue
import threading
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..logging_setup import get_logger, HardwareUnavailableError

log = get_logger("hardware.audio")

SAMPLE_RATE = 16000
CHANNELS = 1

try:  # pragma: no cover - depends on system PortAudio
    import sounddevice as sd
    _SD = True
except Exception:  # pragma: no cover
    sd = None  # type: ignore
    _SD = False


def portaudio_available() -> bool:
    return _SD


def list_input_devices() -> list[dict]:
    if not _SD:
        return []
    out = []
    try:
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                out.append({"index": i, "name": d["name"],
                            "channels": d["max_input_channels"],
                            "default_rate": d["default_samplerate"]})
    except Exception as e:  # pragma: no cover
        log.warning("query_devices failed: %s", e)
    return out


def list_output_devices() -> list[dict]:
    if not _SD:
        return []
    out = []
    try:
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_output_channels", 0) > 0:
                out.append({"index": i, "name": d["name"],
                            "channels": d["max_output_channels"],
                            "default_rate": d["default_samplerate"]})
    except Exception as e:  # pragma: no cover
        log.warning("query_devices failed: %s", e)
    return out


def rms_level(samples: np.ndarray) -> float:
    """RMS level of an int16/float audio buffer normalized to 0..1."""
    if samples.size == 0:
        return 0.0
    x = samples.astype(np.float32)
    if np.issubdtype(samples.dtype, np.integer):
        x = x / 32768.0
    return float(np.sqrt(np.mean(np.square(x))))


def frames_to_wav_bytes(frames: list[np.ndarray], sample_rate: int = SAMPLE_RATE) -> bytes:
    pcm = np.concatenate(frames) if frames else np.zeros(0, dtype=np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.astype(np.int16).tobytes())
    return buf.getvalue()


def wav_bytes_to_frames(data: bytes, frame_ms: int = 30,
                        sample_rate: int = SAMPLE_RATE) -> list[np.ndarray]:
    """Decode WAV bytes into fixed-size int16 numpy frames."""
    with wave.open(io.BytesIO(data), "rb") as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    n = int(sample_rate * frame_ms / 1000)
    return [pcm[i:i + n] for i in range(0, len(pcm), n)]


class MicrophoneManager:
    """Streaming microphone capture with a queue of 30 ms frames."""

    def __init__(self, device_index: Optional[int] = None,
                 sample_rate: int = SAMPLE_RATE, frame_ms: int = 30):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self._q: queue.Queue[np.ndarray] = queue.Queue(maxsize=500)
        self._stream = None
        self._running = threading.Event()

    @staticmethod
    def is_available() -> bool:
        return _SD and len(list_input_devices()) > 0

    def _callback(self, indata, frames, time_info, status):  # pragma: no cover - needs hw
        if status:
            log.debug("mic status: %s", status)
        try:
            self._q.put_nowait(indata.copy().reshape(-1))
        except queue.Full:
            pass

    def start(self) -> None:
        if not _SD:
            raise HardwareUnavailableError(
                "PortAudio/sounddevice is not available on this system"
            )
        if self._running.is_set():
            return
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=CHANNELS,
                dtype="int16",
                blocksize=int(self.sample_rate * self.frame_ms / 1000),
                device=self.device_index,
                callback=self._callback,
            )
            self._stream.start()
        except Exception as e:
            raise HardwareUnavailableError(f"Microphone open failed: {e}") from e
        self._running.set()

    def stop(self) -> None:
        self._running.clear()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def read_frames(self, max_frames: int = 100) -> list[np.ndarray]:
        out = []
        while len(out) < max_frames:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                break
        return out

    def record_seconds(self, seconds: float) -> bytes:
        """Blocking capture of a fixed duration; returns WAV bytes."""
        if not _SD:
            raise HardwareUnavailableError("PortAudio/sounddevice is not available")
        n = int(self.sample_rate * seconds)
        try:
            data = sd.rec(n, samplerate=self.sample_rate, channels=CHANNELS,
                          dtype="int16", device=self.device_index)
            sd.wait()
        except Exception as e:
            raise HardwareUnavailableError(f"Microphone record failed: {e}") from e
        return frames_to_wav_bytes([data.reshape(-1)], self.sample_rate)

    @property
    def status(self) -> dict:
        return {"running": self._running.is_set(), "device": self.device_index,
                "sample_rate": self.sample_rate, "portaudio": _SD}


class AudioOutputManager:
    """Plays int16 WAV audio to the default (or selected) output device."""

    def __init__(self, device_index: Optional[int] = None, volume: float = 1.0):
        self.device_index = device_index
        self.volume = max(0.0, min(1.5, volume))
        self._stop_flag = threading.Event()

    @staticmethod
    def is_available() -> bool:
        return _SD and len(list_output_devices()) > 0

    def play_wav(self, data: bytes, block: bool = True) -> None:
        if not _SD:
            raise HardwareUnavailableError("PortAudio/sounddevice is not available")
        frames = wav_bytes_to_frames(data)
        pcm = np.concatenate(frames) if frames else np.zeros(0, dtype=np.int16)
        pcm = (pcm.astype(np.float32) * self.volume).clip(-32768, 32767).astype(np.int16)
        self._stop_flag.clear()
        try:
            sd.play(pcm, samplerate=SAMPLE_RATE, device=self.device_index)
        except Exception as e:
            raise HardwareUnavailableError(f"Audio playback failed: {e}") from e
        if block:
            while sd.get_stream().active and not self._stop_flag.is_set():
                threading.Event().wait(0.05)
            sd.stop()

    def stop(self) -> None:
        self._stop_flag.set()
        if _SD:
            try:
                sd.stop()
            except Exception:
                pass
