import re


DEFAULT_MEDICATIONS = {
    'procrastinol': 'blue',
    'debugitol': 'blue_white',
    "sleepn't": 'green_white',
    'sleepnt': 'green_white',
}

DEFAULT_DEMO_PLACEMENT = {
    'blue': 'monday',
    'blue_white': 'tuesday',
    'green_white': 'tuesday',
}

CANONICAL_MEDICATIONS = ('ProcrastiNol', 'Debugitol', "Sleepn't")


def _norm(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower())


def load_medication_map(raw):
    if not raw:
        return dict(DEFAULT_MEDICATIONS)
    return {_norm(k): v for k, v in raw.items()}


def load_demo_placement(raw):
    if not raw:
        return dict(DEFAULT_DEMO_PLACEMENT)
    return dict(raw)


def load_allowed_medications(raw):
    if raw:
        return list(raw)
    return list(CANONICAL_MEDICATIONS)


def canonical_medication_name(name, med_map=None):
    med_map = med_map or DEFAULT_MEDICATIONS
    if medication_to_pill(name, med_map) is None:
        return None
    key = _norm(name)
    for canonical in CANONICAL_MEDICATIONS:
        ckey = _norm(canonical)
        if ckey == key or ckey in key or key in ckey:
            return canonical
    return None


def medication_to_pill(name, med_map=None):
    med_map = med_map or DEFAULT_MEDICATIONS
    key = _norm(name)
    if key in med_map:
        return med_map[key]
    for pattern, pill in med_map.items():
        if pattern in key or key in pattern:
            return pill
    return None


def parse_prescription_meds(names, med_map=None):
    med_map = med_map or DEFAULT_MEDICATIONS
    plan = []
    seen = set()
    for name in names:
        pill = medication_to_pill(name, med_map)
        if pill is None:
            continue
        if pill in seen:
            continue
        seen.add(pill)
        canonical = canonical_medication_name(name, med_map) or name
        plan.append({'medication': canonical, 'pill': pill})
    return plan
