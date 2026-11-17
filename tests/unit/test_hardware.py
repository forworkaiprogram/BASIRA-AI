import numpy as np
import pytest

from basira.hardware.camera import CameraManager
from basira.hardware.device_manager import DeviceManager
from basira.hardware.microphone import (
    AudioOutputManager,
    MicrophoneManager,
    frames_to_wav_bytes,
    list_input_devices,
    list_output_devices,
    portaudio_available,
    rms_level,
    wav_bytes_to_frames,
)


def test_list_cameras_empty_in_sandbox():
    cams = CameraManager.list_cameras()
    assert isinstance(cams, list)


def test_camera_start_without_device_raises():
    mgr = CameraManager(0)
    if mgr.is_available():
        pytest.skip("a real camera exists in this environment")
    with pytest.raises(Exception):
        mgr.start()
    assert mgr.status["running"] is False


def test_camera_probe_nonexistent_index():
    assert not CameraManager.list_cameras_probe(99)


def test_rms_level():
    assert rms_level(np.zeros(1000, dtype=np.int16)) == 0.0
    loud = (np.ones(1000) * 16384).astype(np.int16)
    assert 0.4 < rms_level(loud) <= 0.6
    assert rms_level(np.zeros(0, dtype=np.int16)) == 0.0


def test_wav_roundtrip():
    frames = [np.full(480, 1000, dtype=np.int16),
              np.full(480, -1000, dtype=np.int16)]
    data = frames_to_wav_bytes(frames, 16000)
    back = wav_bytes_to_frames(data, 30, 16000)
    total = np.concatenate(back)
    assert total[0] == 1000 and total[480] == -1000
    assert len(back) == 2 and len(back[0]) == 480


def test_mic_unavailable_raises_or_skips():
    if MicrophoneManager.is_available():
        pytest.skip("real microphone present")
    mgr = MicrophoneManager()
    with pytest.raises(Exception):
        mgr.start()
    assert mgr.status["running"] is False


def test_speaker_unavailable_raises_or_skips():
    if AudioOutputManager.is_available():
        pytest.skip("real speaker present")
    out = AudioOutputManager()
    with pytest.raises(Exception):
        out.play_wav(frames_to_wav_bytes([np.zeros(480, dtype=np.int16)]))


def test_device_manager_scan_graceful():
    dm = DeviceManager()
    report = dm.scan()
    assert isinstance(report.cameras, list)
    assert isinstance(report.microphones, list)
    assert report.portaudio == portaudio_available()
    dm.shutdown()


def test_device_manager_lazy_singletons():
    dm = DeviceManager()
    cam = dm.camera()
    assert dm.camera() is cam
    mic = dm.microphone()
    assert dm.microphone() is mic
    dm.shutdown()
    assert dm._camera is None
