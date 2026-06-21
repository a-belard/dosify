import base64
import json
import os
import re

from dosify.medications import (
    load_allowed_medications, load_medication_map,
    parse_prescription_meds, canonical_medication_name)


def build_scan_prompt(allowed_names):
    listed = '\n'.join('- {}'.format(name) for name in allowed_names)
    return """You are reading a prescription image for a pill-dispensing demo.

ONLY return medications from this allowed list (use these exact spellings):
{}
Rules:
- Include a drug ONLY if it clearly appears on the prescription.
- Do NOT invent drugs. Do NOT return anything outside the list above.
- Ignore all other medication names completely.
- If handwriting is close to a listed name, map it to the matching allowed name.

Return ONLY valid JSON (no markdown):
{{"medications": ["ProcrastiNol"]}}

If none of the allowed drugs appear, return {{"medications": []}}.""".format(listed)


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


def scan_prescription_image(image_path, med_map=None, allowed_names=None, model=None):
    _load_env()
    model = model or os.environ.get('OPENAI_MODEL', 'gemini/gemini-2.5-flash-lite')
    med_map = med_map or load_medication_map(None)
    allowed_names = allowed_names or load_allowed_medications(None)
    prompt = build_scan_prompt(allowed_names)

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
                {'type': 'text', 'text': prompt},
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

    filtered = []
    seen = set()
    for name in names:
        canonical = canonical_medication_name(name, med_map)
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        filtered.append(canonical)

    return {
        'raw_names': filtered,
        'plan': parse_prescription_meds(filtered, med_map),
    }
