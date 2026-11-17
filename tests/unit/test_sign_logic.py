import numpy as np
import pytest

from basira.engines.sign.hand_tracker import (
    INDEX_MCP, INDEX_TIP, MIDDLE_TIP, PINKY_MCP, PINKY_TIP, RING_TIP,
    THUMB_TIP, WRIST,
)
from basira.engines.sign.recognizer import (
    classify_static_gesture,
    fingers_extended,
    normalize_landmarks,
)
from basira.engines.sign.sequence import (
    SequenceBuffer,
    SequenceRecognizer,
    dtw_distance,
)
from basira.engines.sign.dataset_tools import (
    SignDatasetWriter,
    Vocabulary,
    augment_sequence,
    build_templates_from_jsonl,
    load_jsonl,
    split_dataset,
)


def make_hand(extended: tuple[bool, bool, bool, bool, bool],
              thumb_up: bool = True) -> np.ndarray:
    """Synthetic 21-landmark hand: fingers at fixed slots.

    Slots (x): thumb 0.15, index 0.35, middle 0.5, ring 0.65, pinky 0.8.
    Extended finger tips at y=0.1, folded tips at y=0.45 (wrist at 0.6).
    A folded thumb crosses the palm (tip near [0.35, 0.55]).
    """
    lm = np.zeros((21, 3), dtype=np.float32)
    lm[WRIST] = [0.5, 0.6, 0]
    tips_y = {4: 0.1 if extended[0] else 0.55, 8: 0.1 if extended[1] else 0.45,
              12: 0.1 if extended[2] else 0.45, 16: 0.1 if extended[3] else 0.45,
              20: 0.1 if extended[4] else 0.45}
    xs = {4: 0.15, 8: 0.35, 12: 0.5, 16: 0.65, 20: 0.8}
    if not extended[0]:
        xs = {**xs, 4: 0.35}   # folded thumb lies across the palm
    for tip, y in tips_y.items():
        lm[tip] = [xs[tip], y, 0]
    # pips at mid height, aligned with their finger's x slot
    pip_x = {2: xs[4], 6: xs[8], 10: xs[12], 14: xs[16], 18: xs[20]}
    for pip in [2, 6, 10, 14, 18]:
        lm[pip] = [pip_x[pip], 0.35, 0]
    # mcps
    lm[INDEX_MCP] = [0.35, 0.5, 0]
    lm[9] = [0.5, 0.5, 0]
    lm[13] = [0.65, 0.5, 0]
    lm[PINKY_MCP] = [0.8, 0.5, 0]
    # thumb direction: up or down
    if extended[0]:
        lm[THUMB_TIP] = [0.15, 0.1 if thumb_up else 0.75, 0]
    return lm


def test_fingers_extended_open_palm():
    lm = make_hand((True, True, True, True, True))
    assert fingers_extended(lm) == [True] * 5


def test_fingers_extended_fist():
    lm = make_hand((False, False, False, False, False))
    assert fingers_extended(lm) == [False] * 5


def test_classify_gestures():
    cases = {
        (True, True, True, True, True): "open_palm",
        (False, False, False, False, False): "fist",
        (False, True, False, False, False): "pointing",
        (False, True, True, False, False): "victory",
        (True, False, False, False, False): "thumbs_up",
        (True, False, False, True, True): "unknown",
    }
    for ext, expected in cases.items():
        pred = classify_static_gesture(make_hand(ext))
        assert pred.label == expected, f"{ext}: got {pred.label}"


def test_thumbs_down():
    pred = classify_static_gesture(make_hand((True, False, False, False, False),
                                             thumb_up=False))
    assert pred.label == "thumbs_down"


def test_normalize_landmarks_invariant():
    lm = make_hand((True, True, True, True, True))
    shifted = lm.copy()
    shifted[:, :2] += np.array([3.0, -2.0])
    scaled = lm.copy()
    scaled[:, :2] *= 4.0
    n1, n2, n3 = normalize_landmarks(lm), normalize_landmarks(shifted), \
        normalize_landmarks(scaled)
    assert np.allclose(n1, n2, atol=1e-5)
    assert np.allclose(n1, n3, atol=1e-5)


def test_dtw_distance_self_zero():
    seq = make_wave_sequence(20)
    assert dtw_distance(seq, seq) < 1e-6


def test_dtw_discriminates_sequences():
    a = make_wave_sequence(20)
    b = make_fist_sequence(20)
    assert dtw_distance(a, a) < dtw_distance(a, b)


def make_wave_sequence(n_frames: int = 15) -> np.ndarray:
    """A realistic dynamic sign: open palm waving (tilt left-right)."""
    frames = []
    for i in range(n_frames):
        lm = make_hand((True, True, True, True, True))
        offset = 0.03 * np.sin(2 * np.pi * i / n_frames)
        lm[:, 0] += offset
        frames.append(normalize_landmarks(lm))
    return np.stack(frames).reshape(n_frames, 42).astype(np.float32)


def make_fist_sequence(n_frames: int = 15) -> np.ndarray:
    frames = []
    for i in range(n_frames):
        lm = make_hand((False, False, False, False, False))
        frames.append(normalize_landmarks(lm))
    return np.stack(frames).reshape(n_frames, 42).astype(np.float32)


def test_sequence_recognizer_matches_template():
    template = make_wave_sequence()
    rec = SequenceRecognizer(threshold=0.05)
    rec.add_template("hello", template)
    rng = np.random.default_rng(2)
    noisy = template + rng.normal(0, 0.002, template.shape).astype(np.float32)
    buf = SequenceBuffer(min_frames=8)
    for frame in noisy:
        buf.push(frame.reshape(21, 2))
    result = rec.recognize(buf)
    assert result.label == "hello"
    assert result.confidence > 0.5


def test_sequence_recognizer_rejects_unknown():
    rec = SequenceRecognizer(threshold=0.05)
    rec.add_template("hello", make_wave_sequence())
    buf = SequenceBuffer(min_frames=8)
    for frame in make_fist_sequence():
        buf.push(frame.reshape(21, 2))
    result = rec.recognize(buf)
    assert result.label is None


def test_sequence_cooldown_suppresses_repeats():
    template = make_wave_sequence()
    rec = SequenceRecognizer(threshold=0.05, cooldown_frames=10)
    rec.add_template("hello", template)
    buf = SequenceBuffer(min_frames=8)
    for frame in template:
        buf.push(frame.reshape(21, 2))
    first = rec.recognize(buf)
    second = rec.recognize(buf)
    assert first.label == "hello"
    assert second.label is None  # suppressed by cooldown


def test_template_validation():
    rec = SequenceRecognizer()
    with pytest.raises(ValueError):
        rec.add_template("x", np.zeros((3, 42), dtype=np.float32))
    with pytest.raises(ValueError):
        rec.add_template("x", np.zeros((10, 41), dtype=np.float32))


def test_vocabulary_roundtrip(tmp_path):
    vocab = Vocabulary.load(tmp_path / "v.json")
    vocab.add("hello", "مرحبا", "hello")
    vocab.record_sample("hello")
    vocab.save(tmp_path / "v.json")
    v2 = Vocabulary.load(tmp_path / "v.json")
    assert v2.entries["hello"]["samples"] == 1
    with pytest.raises(ValueError):
        v2.add("hello", "x", "x")
    with pytest.raises(ValueError):
        v2.record_sample("missing")


def test_dataset_writer_requires_consent(tmp_path):
    writer = SignDatasetWriter(tmp_path / "rec.jsonl")
    frames = np.zeros((10, 42), dtype=np.float32)
    with pytest.raises(ValueError):
        writer.append("hello", frames, consent_id="")
    n = writer.append("hello", frames, consent_id="consent-123")
    assert n == 10
    samples = load_jsonl(tmp_path / "rec.jsonl")
    assert samples[0]["consent_id"] == "consent-123"


def test_split_dataset_stratified():
    samples = []
    for label in ["a", "b"]:
        for i in range(10):
            samples.append({"label": label, "frames": [[0.0] * 42] * 5})
    tr, va, te = split_dataset(samples)
    assert len(tr) + len(va) + len(te) == 20
    tr_labels = {s["label"] for s in tr}
    assert tr_labels == {"a", "b"}


def test_augment_preserves_shape():
    frames = np.random.default_rng(0).normal(0, 0.01, (12, 42)).astype(np.float32)
    import random
    out = augment_sequence(frames, random.Random(1))
    assert out.shape == frames.shape
    assert not np.array_equal(out, frames)


def test_build_templates(tmp_path):
    writer = SignDatasetWriter(tmp_path / "rec.jsonl")
    rng = np.random.default_rng(5)
    for label in ["hello", "thanks"]:
        for _ in range(3):
            writer.append(label, rng.normal(0, 0.01, (12, 42)).astype(np.float32),
                          consent_id="c1")
    templates = build_templates_from_jsonl(tmp_path / "rec.jsonl",
                                           max_per_label=2, augment=1)
    labels = [t[0] for t in templates]
    assert labels.count("hello") == 4  # 2 real + 2 augmented
