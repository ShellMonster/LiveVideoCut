# Decisions — live-stream-clipper

## 2026-04-09 Architecture Decisions
- Three-level pipeline: PySceneDetect → FashionSigLIP → Qwen-VL-Plus → FunASR
- ONNX Runtime over PyTorch for smaller Docker images
- FashionSigLIP over CLIP ViT-B/32 for better fashion detection (+57%)
- Adaptive threshold over fixed 0.85 for clothing scenarios
- PySceneDetect pre-filtering over global frame extraction
- 5-dimension structured VLM prompt over simple "is different?" prompt
- 60s cooldown to prevent transition-period false positives
- VLM > ASR > VLM-description fallback for product naming
