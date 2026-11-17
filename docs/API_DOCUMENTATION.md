# API DOCUMENTATION — BASIRA AI Local Service

الخدمة تعمل على `127.0.0.1:8765` فقط (loopback). كل الطلبات (عدا `/health`)
تتطلب `Authorization: Bearer <token>` — التوكن يُولَّد تلقائياً في أول تشغيل
ويُخزَّن في قاعدة البيانات المحلية: `python scripts/run_server.py --show-token`.

## GET /health
بدون مصادقة. `{"status": "ok", "version": "0.1.0"}`

## GET /status
حالة المحركات ولقطة السياق:
```json
{"engines": [{"name": "vision", "state": "unloaded", "detail": "", "last_latency_ms": null}],
 "context": {"mode": "dashboard", "last_answer": "", "recent": []}}
```

## POST /query
```json
{"request": "أين الهاتف؟", "frame_b64": "<jpeg base64 اختياري>", "language": "ar"}
```
الاستجابة:
```json
{"mode": "vision", "intent": "find", "text": "…", "confidence": 0.85,
 "data": {"detections": [{"name": "cell phone", "confidence": 0.85, "box": [...]}],
          "ocr": "", "warnings": [], "fused_summary": "…"},
 "latency_ms": 412.3}
```
- بدون `frame_b64`: الأسئلة البصرية تُجاب برسالة توجيه.
- أخطاء: 400 (طلب فارغ/إطار غير صالح)، 401 (توكن).

## POST /tts
```json
{"text": "مرحبا"}
```
→ `{"wav_b64": "...", "sample_rate": 22050}` أو 503 إن كان TTS غير مثبت.

## WS /ws?token=<token>
- `{"type":"query","request":"..."}` → `{"type":"answer","text":"...","mode":"..."}`
- `{"type":"ping"}` → `{"type":"pong"}`
- توكن خاطئ: إغلاق برمز 4401.

## الاستخدام المباشر من Python (بدون HTTP)
```python
from basira.intelligence.orchestrator import BASIRACore
core = BASIRACore(db, settings)
resp = core.handle_request("أين الهاتف؟", frame)   # frame: BGR numpy
```
