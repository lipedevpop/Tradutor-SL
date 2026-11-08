import json
from deepl_api import DATA

def load_settings():
    try:
        return json.loads((DATA / 'settings.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    DATA.mkdir(parents=True, exist_ok=True)
    temp = DATA / 'settings.tmp'
    temp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(DATA / 'settings.json')
