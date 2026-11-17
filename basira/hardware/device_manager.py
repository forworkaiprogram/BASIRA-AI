"""Unified device management for cameras, microphones and speakers."""
from __future__ import annotations

from dataclasses import dataclass, field

from .camera import CameraManager, CameraInfo
from .microphone import (
    AudioOutputManager,
    MicrophoneManager,
    list_input_devices,
    list_output_devices,
    portaudio_available,
)


@dataclass
class DeviceReport:
    cameras: list[CameraInfo] = field(default_factory=list)
    microphones: list[dict] = field(default_factory=list)
    speakers: list[dict] = field(default_factory=list)
    portaudio: bool = False

    def to_dict(self) -> dict:
        return {
            "cameras": [c.__dict__ for c in self.cameras],
            "microphones": self.microphones,
            "speakers": self.speakers,
            "portaudio": self.portaudio,
        }


class DeviceManager:
    """Single entry point for discovering and selecting hardware."""

    def __init__(self, camera_index: int = 0, mic_index: int | None = None,
                 speaker_index: int | None = None):
        self.camera_index = camera_index
        self.mic_index = mic_index
        self.speaker_index = speaker_index
        self._camera: CameraManager | None = None
        self._mic: MicrophoneManager | None = None
        self._speaker: AudioOutputManager | None = None

    def scan(self) -> DeviceReport:
        report = DeviceReport(portaudio=portaudio_available())
        try:
            report.cameras = CameraManager.list_cameras()
        except Exception:
            report.cameras = []
        if portaudio_available():
            report.microphones = list_input_devices()
            report.speakers = list_output_devices()
        return report

    # -- lazy singletons ------------------------------------------------------
    def camera(self, width: int = 1280, height: int = 720, fps: int = 30) -> CameraManager:
        if self._camera is None:
            self._camera = CameraManager(self.camera_index, width, height, fps)
        return self._camera

    def microphone(self) -> MicrophoneManager:
        if self._mic is None:
            self._mic = MicrophoneManager(self.mic_index)
        return self._mic

    def speaker(self, volume: float = 1.0) -> AudioOutputManager:
        if self._speaker is None:
            self._speaker = AudioOutputManager(self.speaker_index, volume)
        return self._speaker

    def shutdown(self) -> None:
        for dev in (self._camera, self._mic, self._speaker):
            if dev is not None:
                try:
                    dev.stop()
                except Exception:
                    pass
        self._camera = self._mic = self._speaker = None
