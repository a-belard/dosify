import base64
import json
import os
import re

from dosify.medications import parse_prescription_meds, load_medication_map

SCAN_PROMPT = """You are reading a handwritten or printed prescription image.
Extract every medication name you can see.

Return ONLY valid JSON (no markdown):
{"medications": ["Name1", "Name2"]}

Use the exact spelling visible in the image. If none found, return {"medications": []}."""


def _load_env():
    try:
        from dotenv import load_dotenv
        pkg = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        load_dotenv(os.path.join(pkg, '.env'))
    except ImportError:
        pass


def _client():
    _load_env()
    from openai import OpenAI
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY not set (add to dosify/.env)')
    base_url = os.environ.get(
        'OPENAI_BASE_URL', 'https://ai-gateway.andrew.cmu.edu').strip()
    return OpenAI(api_key=api_key, base_url=base_url)


def _parse_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return json.loads(text)


def scan_prescription_image(image_path, med_map=None, model=None):
    _load_env()
    model = model or os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

    with open(image_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')

    ext = os.path.splitext(image_path)[1].lower()
    mime = 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/png'

    client = _client()
    resp = client.chat.completions.create(
        model=model,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': SCAN_PROMPT},
                {'type': 'image_url', 'image_url': {
                    'url': 'data:{};base64,{}'.format(mime, b64)}},
            ],
        }],
        max_tokens=300,
    )

    raw = resp.choices[0].message.content or ''
    data = _parse_json(raw)
    names = data.get('medications') or []
    if not isinstance(names, list):
        raise RuntimeError('Unexpected scan response: {!r}'.format(data))

    med_map = med_map or load_medication_map(None)
    return {
        'raw_names': names,
        'plan': parse_prescription_meds(names, med_map),
    }
