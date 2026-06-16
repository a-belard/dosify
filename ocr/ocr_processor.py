"""
Dosify OCR Processor
Extracts medication information from prescription images using Google Gemini Vision API.
"""

import os
import json
import time
import sys
from pathlib import Path

try:
    from google import genai
except ImportError:
    print("ERROR: google-genai not installed. Run: pip install google-genai")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except Exception:
    PYTESSERACT_AVAILABLE = False

# ANSI color codes for CLI output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg"}
MAX_RETRIES = 3
CONFIDENCE_THRESHOLD = 85
DEFAULT_GEMINI_MODEL = "gemini-2.5-pro"

GEMINI_PROMPT = """You are a medical prescription analyzer. Extract medication information from the prescription image provided. Return ONLY valid JSON (no markdown, no explanation). If a field cannot be found, use null. For ambiguous text, include "uncertain": true. Extract exactly these fields: medication_name, dosage_amount, frequency, special_instructions. Ensure JSON is parseable.

The response must be a JSON array of medication objects. Each object must have:
- medication_name: string or null
- dosage_amount: string or null
- frequency: string or null
- special_instructions: string or null
- uncertain: boolean (true if any field was ambiguous)
- confidence: object with keys name, dosage, frequency, instructions — each an integer 0-100

Focus ONLY on prescription medication information. If multiple medications are present, include all of them."""


def color_confidence(score: int) -> str:
    """Return ANSI-colored confidence score string."""
    if score >= 90:
        return f"{GREEN}{score}%{RESET}"
    elif score >= 85:
        return f"{YELLOW}{score}%{RESET}"
    else:
        return f"{RED}{score}%{RESET}"


def validate_image(image_path: str) -> Path:
    """
    Validate that the image file exists and has a supported format.

    Args:
        image_path: Path to the prescription image file.

    Returns:
        Resolved Path object.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is not supported.
    """
    path = Path(image_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {image_path}")
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format '{path.suffix}'. Supported: {', '.join(SUPPORTED_FORMATS)}"
        )
    return path


def load_image(image_path: Path) -> Image.Image:
    """
    Load image using Pillow, converting to RGB if needed.

    Args:
        image_path: Validated Path to the image file.

    Returns:
        PIL Image object.
    """
    img = Image.open(image_path)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def call_gemini_with_retry(client, model_name: str, image: Image.Image) -> tuple[str, int]:
    """
    Send image to Gemini Vision API with up to MAX_RETRIES attempts.

    Args:
        client: Configured google.genai Client instance.
        model_name: Gemini model name string.
        image: PIL Image to analyze.

    Returns:
        Tuple of (raw response text, attempt count used).

    Raises:
        RuntimeError: If all retry attempts fail.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[GEMINI_PROMPT, image],
            )
            return response.text, attempt
        except Exception as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(f"  Attempt {attempt} failed ({exc}). Retrying in {wait}s...")
                time.sleep(wait)

    raise RuntimeError(
        f"Gemini API failed after {MAX_RETRIES} attempts. Last error: {last_error}"
    )


def parse_gemini_response(raw_text: str) -> list[dict]:
    """
    Parse and validate Gemini's JSON response.

    Strips markdown code fences if present before parsing.

    Args:
        raw_text: Raw string returned by Gemini.

    Returns:
        List of medication dicts.

    Raises:
        ValueError: If the response cannot be parsed as valid JSON or is malformed.
    """
    text = raw_text.strip()

    # Strip markdown fences if Gemini wrapped the JSON
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned non-JSON response: {exc}\nRaw: {raw_text[:300]}")

    # Gemini may return a single dict or a list
    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array of medications, got: {type(data).__name__}")

    return data


def normalize_medication(raw: dict) -> dict:
    """
    Normalize a single medication entry from Gemini into the Dosify output schema.

    Fills in default confidence values (50) for any missing keys so the output
    is always fully populated.

    Args:
        raw: Raw medication dict from Gemini.

    Returns:
        Normalized medication dict conforming to the Dosify output schema.
    """
    conf_raw = raw.get("confidence", {})
    confidence = {
        "name": int(conf_raw.get("name", 50)),
        "dosage": int(conf_raw.get("dosage", 50)),
        "frequency": int(conf_raw.get("frequency", 50)),
        "instructions": int(conf_raw.get("instructions", 50)),
    }

    return {
        "name": raw.get("medication_name"),
        "dosage": raw.get("dosage_amount"),
        "frequency": raw.get("frequency"),
        "special_instructions": raw.get("special_instructions"),
        "confidence": confidence,
        "uncertain": bool(raw.get("uncertain", False)),
    }


def compute_overall_confidence(medications: list[dict]) -> int:
    """
    Compute overall confidence as the mean of all individual field scores.

    Args:
        medications: List of normalized medication dicts.

    Returns:
        Integer overall confidence score 0-100.
    """
    if not medications:
        return 0
    scores = []
    for med in medications:
        scores.extend(med["confidence"].values())
    return round(sum(scores) / len(scores))


def parse_local_ocr(text: str) -> list[dict]:
    """
    Lightweight heuristic parser for OCR text to extract medication-like lines.

    Returns a list of medication dicts with best-effort fields and conservative confidences.
    """
    import re

    meds = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Heuristics: look for lines that contain a medication name + dosage (e.g., "Metformin 500mg")
    med_line_re = re.compile(r"(?P<name>[A-Za-z0-9\-\s]+?)\s+(?P<dosage>\d+\s*(mg|mcg|g|ml|mL))", re.I)
    freq_re = re.compile(r"(once daily|twice daily|daily|every \d+ (hours|hrs)|at bedtime|qhs|qid|bid)", re.I)

    for line in lines:
        m = med_line_re.search(line)
        if m:
            name = m.group('name').strip()
            dosage = m.group('dosage').strip()
            freq_m = freq_re.search(line)
            frequency = freq_m.group(0) if freq_m else None
            meds.append({
                "name": name,
                "dosage": dosage,
                "frequency": frequency,
                "special_instructions": None,
                "confidence": {"name": 70, "dosage": 75, "frequency": 60, "instructions": 50},
                "uncertain": False if frequency else True,
            })

    # If no meds found, return a single uncertain entry with full OCR text in special_instructions
    if not meds:
        meds = [
            {
                "name": None,
                "dosage": None,
                "frequency": None,
                "special_instructions": text[:1000],
                "confidence": {"name": 50, "dosage": 50, "frequency": 50, "instructions": 40},
                "uncertain": True,
            }
        ]

    return meds


def extract_medications(image_path: str, use_local: bool = False) -> dict:
    """
    Full pipeline: validate image → call Gemini → parse → return structured JSON.

    Args:
        image_path: Path to the prescription image file.

    Returns:
        Dosify output dict with keys: success, medications, overall_confidence,
        requires_confirmation, raw_ocr_text, processing_time_ms.
    """
    start_ms = time.time() * 1000

    # --- Load .env if present ---
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    # --- Setup Gemini ---
    api_key = os.environ.get("GOOGLE_API_KEY")

    # --- Validate & load image ---
    path = validate_image(image_path)
    image = load_image(path)

    if api_key and not use_local:
        client = genai.Client(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

        # --- Call API ---
        raw_text, attempts_used = call_gemini_with_retry(client, model_name, image)

        # --- Parse response ---
        raw_medications = parse_gemini_response(raw_text)
        medications = [normalize_medication(m) for m in raw_medications]
    else:
        # Local OCR path using pytesseract
        if not PYTESSERACT_AVAILABLE:
            raise EnvironmentError(
                "pytesseract is not available. Install it or set GOOGLE_API_KEY for Gemini API."
            )
        try:
            raw_text = pytesseract.image_to_string(image)
        except Exception as exc:
            raise RuntimeError(f"Local OCR failed: {exc}")

        # Minimal heuristic: wrap OCR text into a single medication entry for manual review
        medications = [
            {
                "name": None,
                "dosage": None,
                "frequency": None,
                "special_instructions": None,
                "confidence": {"name": 50, "dosage": 50, "frequency": 50, "instructions": 50},
                "uncertain": True,
            }
        ]

    overall = compute_overall_confidence(medications)
    requires_confirmation = overall < CONFIDENCE_THRESHOLD or any(
        m["uncertain"] for m in medications
    )

    processing_time = round(time.time() * 1000 - start_ms)

    return {
        "success": True,
        "medications": medications,
        "overall_confidence": overall,
        "requires_confirmation": requires_confirmation,
        "raw_ocr_text": raw_text,
        "processing_time_ms": processing_time,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def display_results(result: dict) -> None:
    """Pretty-print extraction results to stdout with color-coded confidence."""
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}  Dosify OCR — Extraction Results{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"  Processing time : {result['processing_time_ms']} ms")
    print(
        f"  Overall confidence: {color_confidence(result['overall_confidence'])}"
    )
    print(
        f"  Requires confirmation: "
        f"{'⚠  YES' if result['requires_confirmation'] else 'NO'}"
    )
    print()

    for i, med in enumerate(result["medications"], 1):
        print(f"{BOLD}  Medication #{i}{RESET}")
        print(f"    Name              : {med['name'] or 'N/A'}  "
              f"[{color_confidence(med['confidence']['name'])}]")
        print(f"    Dosage            : {med['dosage'] or 'N/A'}  "
              f"[{color_confidence(med['confidence']['dosage'])}]")
        print(f"    Frequency         : {med['frequency'] or 'N/A'}  "
              f"[{color_confidence(med['confidence']['frequency'])}]")
        print(f"    Special instructions: {med['special_instructions'] or 'N/A'}  "
              f"[{color_confidence(med['confidence']['instructions'])}]")
        if med["uncertain"]:
            print(f"    {YELLOW}⚠  Some fields flagged as uncertain by Gemini{RESET}")
        print()

    if result["requires_confirmation"]:
        print(
            f"{YELLOW}⚠  Overall confidence below {CONFIDENCE_THRESHOLD}% or ambiguous fields detected."
            f"\n   Manual confirmation recommended.{RESET}\n"
        )


def prompt_user_action(result: dict) -> dict:
    """
    Prompt user to confirm, edit, or reject the extracted data.

    Args:
        result: Extraction result dict (mutated in place for edits).

    Returns:
        Updated result dict with 'user_action' key added.
    """
    print("  What would you like to do?")
    print("    [C] Confirm extraction")
    print("    [E] Edit a field")
    print("    [R] Reject (discard results)")
    choice = input("\n  Enter choice [C/E/R]: ").strip().upper()

    if choice == "R":
        result["user_action"] = "rejected"
        print(f"\n  {RED}Extraction rejected.{RESET}")
        return result

    if choice == "E" and result["medications"]:
        med_index = 0
        if len(result["medications"]) > 1:
            try:
                med_index = int(input(f"  Medication number to edit (1-{len(result['medications'])}): ")) - 1
            except ValueError:
                med_index = 0

        med = result["medications"][med_index]
        fields = ["name", "dosage", "frequency", "special_instructions"]
        print("\n  Which field?")
        for fi, f in enumerate(fields, 1):
            print(f"    [{fi}] {f}: {med[f]}")
        try:
            field_choice = int(input("  Field number: ")) - 1
            field_name = fields[field_choice]
            new_val = input(f"  New value for '{field_name}': ").strip()
            result["medications"][med_index][field_name] = new_val or None
            # Manual edit sets confidence to 100 for that field
            conf_key = {"name": "name", "dosage": "dosage",
                        "frequency": "frequency",
                        "special_instructions": "instructions"}[field_name]
            result["medications"][med_index]["confidence"][conf_key] = 100
            result["user_action"] = "edited"
            print(f"  {GREEN}Field updated.{RESET}")
        except (ValueError, IndexError):
            print("  Invalid selection. Confirming without changes.")
            result["user_action"] = "confirmed"
    else:
        result["user_action"] = "confirmed"
        print(f"\n  {GREEN}Extraction confirmed.{RESET}")

    return result


def main() -> None:
    """CLI entry point for Dosify OCR Processor."""
    print(f"\n{BOLD}Dosify OCR Processor{RESET} — Prescription Image Analyzer")
    print("Powered by Google Gemini Vision\n")

    use_local = "--local" in sys.argv

    script_dir = Path(__file__).resolve().parent
    images_dir = script_dir / "images"

    if not images_dir.is_dir():
        print(f"{RED}No 'images' folder found at {images_dir}{RESET}")
        sys.exit(1)

    candidates = sorted(
        [p for p in images_dir.iterdir() if p.suffix.lower() in SUPPORTED_FORMATS],
        key=lambda p: p.name.lower(),
    )

    if not candidates:
        print(f"{RED}No images found in {images_dir}{RESET}")
        print(f"Add .png / .jpg / .jpeg files there and re-run.")
        sys.exit(1)

    print(f"Images in '{images_dir.name}' folder:\n")
    for i, p in enumerate(candidates, 1):
        print(f"  [{i}] {p.name}")

    print()
    while True:
        choice = input(f"Select image number [1-{len(candidates)}]: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                break
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(candidates)}.")

    image_path = str(candidates[idx])
    print(f"\nSelected: {candidates[idx].name}")
    if not image_path:
        print(f"{RED}No image path provided.{RESET}")
        sys.exit(1)

    print(f"\nProcessing: {image_path}")
    print("Sending to Gemini Vision API...\n")

    try:
        result = extract_medications(image_path, use_local=use_local)
    except FileNotFoundError as exc:
        print(f"{RED}File error: {exc}{RESET}")
        sys.exit(1)
    except ValueError as exc:
        print(f"{RED}Validation error: {exc}{RESET}")
        sys.exit(1)
    except EnvironmentError as exc:
        print(f"{RED}Configuration error: {exc}{RESET}")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"{RED}API error: {exc}{RESET}")
        error_output = {
            "success": False,
            "error": str(exc),
            "medications": [],
            "overall_confidence": 0,
            "requires_confirmation": True,
        }
        print(json.dumps(error_output, indent=2))
        sys.exit(1)

    display_results(result)
    result = prompt_user_action(result)

    # Final JSON output
    print(f"\n{BOLD}Final JSON Output:{RESET}")
    # Remove raw_ocr_text from printed output to keep it readable, keep in saved result
    display_result = {k: v for k, v in result.items() if k != "raw_ocr_text"}
    print(json.dumps(display_result, indent=2))

    # Optionally save full result
    save = input("\nSave full result to output.json? [y/N]: ").strip().lower()
    if save == "y":
        with open("output.json", "w") as f:
            json.dump(result, f, indent=2)
        print(f"{GREEN}Saved to output.json{RESET}")


if __name__ == "__main__":
    main()
