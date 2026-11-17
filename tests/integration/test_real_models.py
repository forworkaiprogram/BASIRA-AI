"""Integration tests running REAL models on REAL data.

Model files are required (downloaded by scripts/download_models.py).
Each test skips (does not fail) when its model is absent, but when present
it must produce genuine results.
"""
import numpy as np
import pytest

from basira.config import models_dir

DATA = __import__("pathlib").Path(__file__).resolve().parents[1] / "data"


def _have(path):
    return path.exists()


# ---------------------------------------------------------------- YOLO -------
@pytest.mark.slow
def test_yolo_detects_real_image():
    model = models_dir() / "vision" / "yolov8n.onnx"
    if not _have(model):
        pytest.skip("yolov8n.onnx not downloaded")
    import cv2

    frame = cv2.imread(str(DATA / "bus.jpg"))
    assert frame is not None
    from basira.engines.vision.detector import ObjectDetector

    det = ObjectDetector(model)
    dets = det.detect(frame)
    names = {d.class_name for d in dets}
    assert "person" in names, f"expected person in {names}"
    assert "bus" in names, f"expected bus in {names}"
    for d in dets:
        assert 0.0 < d.confidence <= 1.0
        x1, y1, x2, y2 = d.xyxy
        assert 0 <= x1 < x2 <= frame.shape[1]
        assert 0 <= y1 < y2 <= frame.shape[0]


@pytest.mark.slow
def test_vision_engine_full_pipeline():
    model = models_dir() / "vision" / "yolov8n.onnx"
    if not _have(model):
        pytest.skip("yolov8n.onnx not downloaded")
    import cv2

    from basira.engines.vision.engine import VisionEngine

    engine = VisionEngine(enable_ocr=False)
    frame = cv2.imread(str(DATA / "bus.jpg"))
    res = engine.analyze_frame(frame, question="أين الشخص؟", lang="ar")
    assert res.detections
    assert len(res.description) > 10
    assert "شخص" in res.answer or "person" in res.answer
    assert isinstance(res.warnings, list)


@pytest.mark.slow
def test_scene_description_arabic():
    model = models_dir() / "vision" / "yolov8n.onnx"
    if not _have(model):
        pytest.skip("yolov8n.onnx not downloaded")
    import cv2

    from basira.engines.vision.engine import VisionEngine

    engine = VisionEngine(enable_ocr=False)
    frame = cv2.imread(str(DATA / "bus.jpg"))
    res = engine.analyze_frame(frame, lang="ar")
    assert "أرى" in res.description
    assert "مسافات دقيقة" in res.description


# ----------------------------------------------------------------- OCR -------
@pytest.mark.slow
def test_ocr_english_rendered_text():
    try:
        import easyocr  # noqa: F401
    except Exception:
        pytest.skip("easyocr not installed")
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (640, 160), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
    except Exception:
        font = ImageFont.load_default()
    draw.text((30, 40), "EXIT 2024", fill="black", font=font)
    frame = np.array(img)[:, :, ::-1].copy()  # to BGR

    from basira.engines.vision.ocr import OcrEngine

    ocr = OcrEngine(languages=("en",))
    result = ocr.read(frame)
    assert "2024" in result.text.replace(" ", "") or "EXIT" in result.text.upper()


# --------------------------------------------------------------- Hands -------
@pytest.mark.slow
def test_hand_tracking_real_image():
    model = models_dir() / "sign" / "hand_landmarker.task"
    if not _have(model):
        pytest.skip("hand_landmarker.task not downloaded")
    try:
        import mediapipe  # noqa: F401
    except Exception:
        pytest.skip("mediapipe unavailable")
    import cv2

    from basira.engines.sign.engine import SignEngine
    from basira.engines.sign.recognizer import classify_static_gesture

    engine = SignEngine()
    engine.tracker.load()
    frame = cv2.imread(str(DATA / "thumb_up.jpg"))
    hands = engine.tracker.track(frame)
    assert hands, "expected a hand in thumb_up.jpg"
    pred = classify_static_gesture(hands[0].landmarks)
    assert pred.label == "thumbs_up", f"got {pred.label}"

    frame2 = cv2.imread(str(DATA / "pointing_up.jpg"))
    hands2 = engine.tracker.track(frame2)
    assert hands2, "expected a hand in pointing_up.jpg"


# ----------------------------------------------------------------- STT -------
@pytest.mark.slow
def test_stt_whisper_on_piper_speech():
    voice = models_dir() / "language" / "ar_JO-kareem-medium.onnx"
    if not _have(voice) or not _have(voice.with_suffix(".onnx.json")):
        pytest.skip("piper voice not downloaded")
    try:
        from piper import PiperVoice  # noqa: F401
        from faster_whisper import WhisperModel  # noqa: F401
    except Exception:
        pytest.skip("piper/faster-whisper unavailable")

    from basira.engines.language.tts import TextToSpeech

    tts = TextToSpeech()
    pcm = tts.synthesize("مرحبا")
    assert pcm.size > 8000  # at least ~0.4 s of audio

    from basira.engines.audio.stt import SpeechRecognizer

    stt = SpeechRecognizer(model_size="base")
    transcript = stt.transcribe_pcm(pcm, tts.sample_rate, language="ar")
    assert not transcript.is_empty
    assert transcript.language.startswith("ar")


# ----------------------------------------------------------------- TTS -------
@pytest.mark.slow
def test_tts_synthesis_deterministic():
    voice = models_dir() / "language" / "ar_JO-kareem-medium.onnx"
    if not _have(voice):
        pytest.skip("piper voice not downloaded")
    from basira.engines.language.tts import TextToSpeech

    tts = TextToSpeech()
    pcm1 = tts.synthesize("بصيرة")
    pcm2 = tts.synthesize("بصيرة")
    assert pcm1.size > 8000
    # piper uses a threaded runtime: sizes are close but not bit-identical
    assert abs(pcm1.size - pcm2.size) / pcm1.size < 0.2
