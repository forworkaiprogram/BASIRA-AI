# DATASETS — مصادر البيانات وخط التدريب

## Vision (كشف الأجسام)
- **النموذج الحالي:** YOLOv8n مدرب مسبقاً على COCO (80 صنفاً، AGPL-3.0).
- للتوسع: COCO (coco_dataset), Open Images V9 (CC-BY-2.0), Objects365.
- خط التدريب: `training/vision/` — fine-tuning بـ ultralytics ثم تصدير ONNX
  عبر `scripts/export_yolo_onnx.py`.

## OCR
- **النموذج الحالي:** EasyOCR (craft_mlt_25k + arabic_g2 + english_g2، Apache-2.0).
- بيانات إضافية مقترحة: Arabic Handwritten Text (AHDB), SORRY Arabic text in
  the wild، لافتات عربية مصوّرة بموافقة أصحابها.

## Sign Language
- **الحالي:** لا توجد بيانات مضمنة. تتبع اليد يعمل بنموذج MediaPipe
  (hand_landmarker، Apache-2.0) والإيماءات الثابتة هندسية.
- **ArYSL (لغة الإشارة اليمنية):** يجب التحقق من الترخيص وشروط الاستخدام قبل
  أي استخدام. لا نصف أي بيانات غير يمنية بأنها يمنية.
- **أدوات الجمع:** `basira/engines/sign/dataset_tools.py` (JSONL مع consent_id
  إلزامي) + `scripts/enroll_sign.py`. الصيغة: معالم يد مُسوّاة (42 رقماً/إطار)
  — لا تُخزَّن فيديوهات.
- **خط التدريب:** `training/sign/` — DTW templates (يعمل الآن) وCNN+LSTM/GRU
  على التسلسلات (هيكل جاهز، يحتاج بيانات).

## Audio
- **STT:** Whisper base (faster-whisper، int8) — عربي/إنجليزي.
- **أصوات بيئية:** خط تدريب `training/audio/` على ESC-50 (CC-BY) لمجموعة
  الأصوات المستهدفة (جرس، بوق، بكاء طفل، كسر زجاج…) → تصدير ONNX إلى
  `models/audio/sound_classifier.onnx`. حتى تثبيته يعمل الوضع التقديري
  (بوابة طاقة + كاشف إنذار طيفي، موسوم heuristic).
- كلام عربي إضافي: Common Voice ar (CC-0), MGB-2.

## قواعد إلزامية
1. لا تُخترع نتائج تدريب — كل مقياس في MODEL_CARDS.md مأخوذ من تشغيل فعلي.
2. تسجيلات المشاركين تتطلب consent_id ولا تُرفع أبداً دون موافقة صريحة.
3. Train/Val/Test split مقسّم لكل صنف (stratified) — `split_dataset()`.
