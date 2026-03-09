# Boat Number OCR - Model Selection & Technical Details

## Overview

The **Boat Number OCR** feature scans boat images and extracts the registration number using Optical Character Recognition (OCR). It is designed to read painted, stenciled, or printed text on Indian fishing boats.

**API Endpoint:** `POST /api/v1/port-officer/boats/scan-number`

---

## Why EasyOCR?

After evaluating all major OCR options, **EasyOCR** was selected as the best fit for this project. Below is a detailed comparison of every option considered.

---

## OCR Model Comparison

### 1. EasyOCR (Selected)

| Property | Detail |
|---|---|
| **Type** | Deep learning (CRAFT text detector + CRNN recognizer) |
| **Framework** | PyTorch |
| **Model Size** | ~200 MB (downloaded once, cached locally) |
| **Languages** | 80+ (English, Hindi, Tamil, etc.) |
| **License** | Apache 2.0 (free, commercial use allowed) |
| **GPU Required** | No (works on CPU, faster with GPU) |
| **API Key Required** | No |
| **Best For** | Scene text (painted signs, outdoor text, stenciled boat numbers) |

**Why chosen:**
- Specifically designed for **scene text recognition** -- text painted on boats, signs, walls, etc. This is exactly our use case.
- Uses **CRAFT** (Character Region Awareness for Text Detection) which excels at detecting individual characters even when spacing is inconsistent.
- The project already uses **PyTorch** (for YOLO/ultralytics), so EasyOCR adds zero new ML frameworks.
- Fully **offline** -- no internet needed after initial model download, no API keys, no recurring costs.
- Supports **80+ languages** including English and Indian regional scripts.

---

### 2. Tesseract / Pytesseract

| Property | Detail |
|---|---|
| **Type** | Traditional OCR + LSTM neural network |
| **Framework** | C++ (with Python wrapper `pytesseract`) |
| **Model Size** | ~30 MB |
| **Languages** | 100+ |
| **License** | Apache 2.0 |
| **GPU Required** | No |
| **API Key Required** | No |
| **Best For** | Clean, printed, scanned documents |

**Why not chosen:**
- Designed for **document OCR** (printed books, scanned PDFs) -- performs poorly on scene text like painted boat numbers.
- Struggles with **angled text, uneven lighting, weathered paint**, and low contrast -- all common in boat images.
- Requires **Tesseract system package** installed on the server (`apt-get install tesseract-ocr`), adding deployment complexity.
- Significantly lower accuracy on outdoor/real-world images compared to deep learning models.

---

### 3. PaddleOCR

| Property | Detail |
|---|---|
| **Type** | Deep learning (DB text detector + CRNN/SVTR recognizer) |
| **Framework** | PaddlePaddle |
| **Model Size** | ~15 MB (lightweight models) to ~150 MB |
| **Languages** | 80+ |
| **License** | Apache 2.0 |
| **GPU Required** | No |
| **API Key Required** | No |
| **Best For** | Scene text, documents, multilingual |

**Why not chosen:**
- Very accurate, competitive with EasyOCR.
- However, it requires **PaddlePaddle** framework (~600 MB+), which is a completely separate ML framework from PyTorch.
- Adding PaddlePaddle alongside PyTorch would **significantly increase** Docker image size and memory usage.
- The marginal accuracy improvement does not justify the heavy additional dependency.

---

### 4. Google Cloud Vision API

| Property | Detail |
|---|---|
| **Type** | Cloud-based AI service |
| **Framework** | Google Cloud SDK |
| **Model Size** | N/A (cloud) |
| **Languages** | 100+ |
| **License** | Proprietary (pay-per-use) |
| **GPU Required** | N/A |
| **API Key Required** | Yes (Google Cloud account) |
| **Best For** | Highest accuracy across all conditions |

**Why not chosen:**
- **Most accurate** option for all text detection scenarios.
- Requires a **Google Cloud account**, API key configuration, and internet connectivity for every request.
- **Pay-per-use pricing**: $1.50 per 1,000 images (first 1,000/month free).
- Adds external dependency -- if Google's API is down or network is unavailable, the feature breaks.
- Not suitable for environments with **limited/no internet** (fishing harbors in remote areas).

---

### 5. RapidOCR

| Property | Detail |
|---|---|
| **Type** | Deep learning (PaddleOCR models converted to ONNX) |
| **Framework** | ONNX Runtime |
| **Model Size** | ~30 MB |
| **Languages** | Chinese, English, multilingual |
| **License** | Apache 2.0 |
| **GPU Required** | No |
| **API Key Required** | No |
| **Best For** | Lightweight deployment, Chinese/English text |

**Why not chosen:**
- Uses **ONNX Runtime** (already in our project), so no new framework needed -- this was the main advantage.
- However, scene text accuracy is **noticeably lower** than EasyOCR, especially for angled or weathered text.
- Primarily optimized for **Chinese text**; English scene text support is secondary.
- Smaller community and less documentation compared to EasyOCR.

---

### 6. Amazon Textract

| Property | Detail |
|---|---|
| **Type** | Cloud-based AI service |
| **Framework** | AWS SDK (boto3) |
| **Model Size** | N/A (cloud) |
| **Languages** | English, Spanish, German, French, Italian, Portuguese |
| **License** | Proprietary (pay-per-use) |
| **GPU Required** | N/A |
| **API Key Required** | Yes (AWS account) |
| **Best For** | Document processing, forms, tables |

**Why not chosen:**
- Optimized for **document processing** (invoices, forms), not scene text on boats.
- Requires AWS account and API keys.
- Pay-per-use pricing.
- Limited language support compared to other options.

---

### 7. Microsoft Azure Computer Vision OCR

| Property | Detail |
|---|---|
| **Type** | Cloud-based AI service |
| **Framework** | Azure SDK |
| **Model Size** | N/A (cloud) |
| **Languages** | 160+ |
| **License** | Proprietary (pay-per-use) |
| **GPU Required** | N/A |
| **API Key Required** | Yes (Azure account) |
| **Best For** | Mixed documents and scene text |

**Why not chosen:**
- Good accuracy for scene text.
- Requires Azure account and API keys.
- Pay-per-use pricing ($1.00 per 1,000 images).
- Same external dependency issues as Google Cloud Vision.

---

## Summary Decision Matrix

| Model | Scene Text Accuracy | Cost | Offline | New Dependencies | Chosen |
|---|---|---|---|---|---|
| **EasyOCR** | High | Free | Yes | None (uses existing PyTorch) | **Yes** |
| Tesseract | Low | Free | Yes | System package | No |
| PaddleOCR | High | Free | Yes | PaddlePaddle (~600MB) | No |
| Google Vision | Highest | Paid | No | API key + internet | No |
| RapidOCR | Medium | Free | Yes | None (uses existing ONNX) | No |
| Amazon Textract | Medium | Paid | No | API key + internet | No |
| Azure Vision | High | Paid | No | API key + internet | No |

---

## How It Works

```
Image Upload
     |
     v
Image Preprocessing (OpenCV)
  - Convert to grayscale
  - CLAHE contrast enhancement
     |
     v
EasyOCR Text Detection (CRAFT)
  - Detects text regions in the image
     |
     v
EasyOCR Text Recognition (CRNN)
  - Reads text from detected regions
  - Returns text + confidence scores
     |
     v
Pattern Matching (Regex)
  - Matches Indian boat registration format:
    [IND-]<STATE>-<DISTRICT>-<CATEGORY>-<SERIAL>
    e.g., IND-TN-12-MM-1234, KA-05-A-0032
     |
     v
Fallback: If no pattern match, return
  highest-confidence detected text as-is
     |
     v
Database Lookup (optional)
  - If boat number found in DB, return full details
```

---

## Indian Fishing Boat Registration Format

Indian fishing boat registration numbers typically follow this structure:

```
[IND-] <State Code> - <District Code> - <Category> - <Serial Number>

Examples:
  IND-TN-12-MM-1234    (Tamil Nadu)
  KA-05-A-0032         (Karnataka)
  IND-KL-08-TT-567     (Kerala)
  MH-03-B-1289         (Maharashtra)
  GJ-15-MM-0456        (Gujarat)
  AP-07-A-2345         (Andhra Pradesh)
```

| Component | Description | Example |
|---|---|---|
| IND | Country prefix (optional) | IND |
| State Code | 2-letter state abbreviation | TN, KA, KL, MH, GJ, AP |
| District Code | 1-2 digit district number | 12, 05, 08 |
| Category | 1-3 letter boat category | MM, A, TT, B |
| Serial Number | 1-5 digit serial | 1234, 0032 |

---

## Configuration

EasyOCR settings in `app/services/boat_scan_service.py`:

| Setting | Value | Description |
|---|---|---|
| Language | `["en"]` | English text detection |
| GPU | `False` | Uses CPU (set to `True` if GPU available) |
| Model cache | `@lru_cache` | Model loaded once, reused for all requests |
| Preprocessing | CLAHE | Contrast Limited Adaptive Histogram Equalization |
