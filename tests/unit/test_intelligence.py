import pytest

from basira.engines.vision.detector import Detection
from basira.intelligence.context_manager import ContextEntry, ContextManager
from basira.intelligence.fusion import MultimodalFusion
from basira.intelligence.router import ModeRouter


def test_context_add_and_trim():
    ctx = ContextManager(max_entries=5)
    for i in range(10):
        ctx.add(ContextEntry("user", "question", f"q{i}"))
    assert len(ctx.entries) == 5
    assert ctx.entries[0].text == "q5"
    assert ctx.recent(3)[0].text == "q7"


def test_context_tracks_last_answer_and_scene():
    ctx = ContextManager()
    ctx.add(ContextEntry("system", "answer", "الإجابة", 0.9))
    ctx.add(ContextEntry("engine", "observation", "مشهد",
                         modality="vision", data={"ocr": "نص"}))
    snap = ctx.snapshot()
    assert snap["last_answer"] == "الإجابة"
    assert snap["last_scene"]["ocr"] == "نص"
    ctx.clear()
    assert ctx.snapshot()["last_answer"] == ""


def test_router_vision_intents():
    router = ModeRouter()
    for q, intent in [("أين الهاتف", "find"), ("اقرأ لي الورقة", "read"),
                      ("كم شخصاً هنا", "count"), ("صف المشهد", "describe"),
                      ("هل طريقي آمن", "obstacle")]:
        d = router.route(q)
        assert d.mode == "vision", q
        assert d.intent == intent, q
        assert "vision.detector" in d.engines


def test_router_hear_and_sign():
    router = ModeRouter()
    assert router.route("ما هذا الصوت").mode == "hear"
    assert router.route("ترجم لغة الإشارة").mode == "sign"
    assert router.route("hello unknown question").mode == "vision"
    assert router.route("hello unknown question").intent == "vqa"


def test_router_no_camera_falls_back():
    router = ModeRouter()
    d = router.route("أين الهاتف", has_camera_frame=False)
    assert d.mode == "hear" or d.mode == "vision"


def test_fusion_objects_and_text():
    f = MultimodalFusion()
    dets = [Detection("person", 0.9, (0, 0, 100, 200)),
            Detection("chair", 0.8, (200, 0, 300, 200))]
    res = f.fuse_scene(detections=dets, ocr_text="خروج", lang="ar")
    assert "شخص" in res.summary
    assert "خروج" in res.summary
    assert len(res.items) == 3
    assert res.conflicts == []


def test_fusion_conflict_sign_without_person():
    f = MultimodalFusion()
    dets = [Detection("chair", 0.8, (0, 0, 100, 100))]
    res = f.fuse_scene(detections=dets, sign_text="مرحبا", lang="ar")
    assert len(res.conflicts) == 1


def test_fusion_no_person_conflict_when_person_present():
    f = MultimodalFusion()
    dets = [Detection("person", 0.9, (0, 0, 100, 100))]
    res = f.fuse_scene(detections=dets, sign_text="مرحبا", lang="ar")
    assert res.conflicts == []


def test_fusion_empty():
    f = MultimodalFusion()
    res = f.fuse_scene(lang="ar")
    assert "لا توجد" in res.summary
