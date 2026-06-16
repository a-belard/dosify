# Dosify OCR Processor

Extracts structured medication information from prescription images using Google Gemini Vision API.

---

## Setup

### 1. Install dependencies

```bash
pip install -r dosify_requirements.txt
```

### 2. Set your Google API key

```bash
export GOOGLE_API_KEY=sk-yLf6QXsqdq-bYQ-I2gJS8Q
```

Get a key at: https://makersuite.google.com/app/apikey

---

## Usage

### Interactive CLI

```bash
python ocr_processor.py
```

### Pass image path as argument

```bash
python ocr_processor.py /path/to/prescription.jpg
```

### Supported formats

`.png`, `.jpg`, `.jpeg`

---

## Output Format

```json
{
  "success": true,
  "medications": [
    {
      "name": "Aspirin",
      "dosage": "500mg",
      "frequency": "twice daily",
      "special_instructions": "with food",
      "confidence": {
        "name": 98,
        "dosage": 95,
        "frequency": 92,
        "instructions": 78
      },
      "uncertain": false
    }
  ],
  "overall_confidence": 91,
  "requires_confirmation": false,
  "raw_ocr_text": "[full Gemini response]",
  "processing_time_ms": 2300,
  "user_action": "confirmed"
}
```

### Field descriptions

| Field | Description |
|---|---|
| `success` | `true` if extraction completed without errors |
| `medications` | Array of extracted medications |
| `overall_confidence` | Mean confidence across all fields (0–100) |
| `requires_confirmation` | `true` if overall confidence < 85% or any field uncertain |
| `raw_ocr_text` | Raw JSON string returned by Gemini |
| `processing_time_ms` | Wall-clock time for the full API round-trip |
| `user_action` | `"confirmed"`, `"edited"`, or `"rejected"` |

---

## Confidence color coding (CLI)

| Color | Score | Meaning |
|---|---|---|
| Green | ≥ 90% | High confidence |
| Yellow | 85–89% | Acceptable, review recommended |
| Red | < 85% | Low confidence — manual confirmation required |

---

## Retry logic

Retries failed Gemini API calls up to **3 times** with exponential backoff (2 s, 4 s).
All attempts failed → structured error JSON printed, exit code 1.

---

## Sample output — successful extraction

```
============================================================
  Dosify OCR — Extraction Results
============================================================
  Processing time : 2341 ms
  Overall confidence: 91%
  Requires confirmation: NO

  Medication #1
    Name              : Metformin  [98%]
    Dosage            : 500mg  [95%]
    Frequency         : twice daily  [92%]
    Special instructions: with food  [78%]
```

## Sample output — failed extraction

```json
{
  "success": false,
  "error": "Gemini API failed after 3 attempts. Last error: ...",
  "medications": [],
  "overall_confidence": 0,
  "requires_confirmation": true
}
```

---

## Programmatic integration

```python
from ocr_processor import extract_medications

result = extract_medications("/path/to/prescription.png")

if result["success"] and not result["requires_confirmation"]:
    for med in result["medications"]:
        print(med["name"], med["dosage"], med["frequency"])
```

---

## Testing tips

- Use clear, well-lit photos of printed prescriptions for best results.
- Handwritten prescriptions typically yield lower confidence — expect `requires_confirmation: true`.
- Measure `processing_time_ms` across runs to baseline API latency.
