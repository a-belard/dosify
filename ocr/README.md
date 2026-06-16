Dosify OCR Processor

This script extracts medication information from prescription images.

Usage

- Place a prescription image (PNG/JPG/JPEG) in the same folder as `ocr_processor.py`.
- To run with local OCR (Tesseract + pytesseract):

  python3 ocr_processor.py --local

  The script will auto-detect an image in the same folder if you don't provide a path.

- To run with Google Gemini Vision API (remote):

  export GOOGLE_API_KEY=your_key
  python3 ocr_processor.py /path/to/image.png

Dependencies

- Python packages (install into your virtualenv):

  pip install -r dosify_requirements.txt

- System dependency for local OCR:

  - Tesseract OCR engine must be installed for pytesseract to work.
    On macOS (Homebrew):

      brew install tesseract

Notes

- If you use `--local`, the script uses pytesseract to extract raw text and wraps it for manual confirmation.
- For full structured extraction, provide a valid `GOOGLE_API_KEY` to use Gemini Vision API.