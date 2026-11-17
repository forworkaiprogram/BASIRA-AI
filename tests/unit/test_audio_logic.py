import time

import numpy as np
import pytest

from basira.engines.audio.alerts import Alert, AlertManager
from basira.engines.audio.sound_events import (
    SoundEventDetector,
    compute_mel_spectrogram,
)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def test_alert_dedup_cooldown():
    clock = FakeClock()
    mgr = AlertManager(default_cooldown=8.0, clock=clock)
    received = []
    mgr.subscribe(received.append)
    a = Alert("sound:doorbell", "جرس الباب")
    assert mgr.raise_alert(a) is True
    assert len(received) == 1
    clock.advance(3)
    assert mgr.raise_alert(a) is False      # suppressed
    clock.advance(6)                        # total 9s > cooldown
    assert mgr.raise_alert(a) is True
    assert len(received) == 2


def test_alert_per_kind_cooldowns():
    clock = FakeClock()
    mgr = AlertManager(default_cooldown=30.0,
                       cooldowns={"sound:fire_alarm": 2.0}, clock=clock)
    assert mgr.raise_alert(Alert("sound:doorbell", "x")) is True
    assert mgr.raise_alert(Alert("sound:fire_alarm", "y")) is True
    clock.advance(3)
    assert mgr.raise_alert(Alert("sound:fire_alarm", "y")) is True   # 3s > 2s
    assert mgr.raise_alert(Alert("sound:doorbell", "x")) is False    # 3s < 30s


def test_alert_history_and_reset():
    clock = FakeClock()
    mgr = AlertManager(default_cooldown=0.0, clock=clock)
    mgr.raise_alert(Alert("a", "t1"))
    clock.advance(1)
    mgr.raise_alert(Alert("a", "t2"))
    assert len(mgr.history) == 2
    mgr.reset()
    assert mgr.history == []


def test_mel_spectrogram_shape():
    sr = 16000
    t = np.arange(sr) / sr
    pcm = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16)
    mel = compute_mel_spectrogram(pcm, sr)
    assert mel.shape[0] == 64
    assert mel.shape[1] > 50


def test_sound_detector_energy_gate():
    det = SoundEventDetector(model_path="/nonexistent/model.onnx")
    det.load()
    silence = np.zeros(1600, dtype=np.int16)
    assert det.detect(silence, 16000, 0.0) is None
    assert det.using_trained_model is False


def test_sound_detector_heuristic_alarm():
    det = SoundEventDetector(model_path="/nonexistent/model.onnx")
    det.load()
    sr = 16000
    t = np.arange(sr) / sr
    # strong 2 kHz tone -> alarm-like band
    tone = (np.sin(2 * np.pi * 2000 * t) * 12000).astype(np.int16)
    event = det.detect(tone, sr, 0.0)
    if event is not None:
        assert event.heuristic is True
        assert 0 < event.confidence < 0.6
    # silence -> nothing
    assert det.detect(np.zeros(sr, dtype=np.int16), sr, 1.0) is None


def test_sound_detector_loads_trained_model(tmp_path):
    pytest.importorskip("onnxruntime")
    import onnx
    import onnx.helper as oh

    # tiny valid classifier: 64 mels x 96 frames -> 8 classes
    graph = oh.make_graph(
        [oh.make_node("Flatten", ["X"], ["F"], axis=1),
         oh.make_node("MatMul", ["F", "W"], ["Y"])],
        "cls",
        [oh.make_tensor_value_info("X", onnx.TensorProto.FLOAT, [1, 1, 64, 96])],
        [oh.make_tensor_value_info("Y", onnx.TensorProto.FLOAT, [1, 8])],
        initializer=[oh.make_tensor("W", onnx.TensorProto.FLOAT,
                                    [64 * 96, 8],
                                    np.zeros((64 * 96, 8), np.float32))],
    )
    model = oh.make_model(graph, opset_imports=[oh.make_opsetid("", 17)])
    model.ir_version = 9
    onnx.save(model, tmp_path / "sound_classifier.onnx")
    det = SoundEventDetector(model_path=tmp_path / "sound_classifier.onnx")
    det.load()
    assert det.using_trained_model is True
    assert det.detect(np.zeros(1600, dtype=np.int16)) is None
