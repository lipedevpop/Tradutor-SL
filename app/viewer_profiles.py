"""Viewer-specific folder hints; the user chooses the actual avatar log folder."""
import os
from pathlib import Path

VIEWERS = ('Alchemy', 'Firestorm', 'Cool VL Viewer')
ROOTS = {
    'Alchemy': ('AlchemyNext', 'Alchemy'),
    'Firestorm': ('Firestorm_x64', 'Firestorm'),
    'Cool VL Viewer': ('SecondLife', 'CoolVLViewer', 'CoolVLViewer_x64'),
}
HELP = {
    'Alchemy': 'Ative o salvamento das IMs nas preferências do Alchemy. Escolha a pasta do avatar com os arquivos .txt.',
    'Firestorm': 'Ative Save IMs em Preferences → Privacy → Logs & Transcripts. Veja a pasta em Network & Files → Directories. Selecione a subpasta do avatar.',
    'Cool VL Viewer': 'Em Preferences → IM, ative Save a log of instant messages on my computer. Confira a pasta ao lado de Change path e selecione a subpasta do avatar.',
}

def browse_start(viewer, current='', appdata=None):
    if current and Path(current).is_dir():
        return Path(current)
    root = Path(appdata or os.environ.get('APPDATA', str(Path.home())))
    for name in ROOTS.get(viewer, ()):
        candidate = root / name
        if candidate.is_dir():
            return candidate
    return root if root.is_dir() else Path.home()


def _settings_log_paths(settings_file):
    """Read only a known preference key; never load chat contents or credentials."""
    import xml.etree.ElementTree as ET
    try:
        if settings_file.stat().st_size > 2 * 1024 * 1024:
            return []
        tree = ET.parse(settings_file)
    except (OSError, ET.ParseError):
        return []
    paths = []
    for mapping in tree.iter('map'):
        nodes = list(mapping)
        for index, key in enumerate(nodes[:-1]):
            if key.tag != 'key' or key.text != 'InstantMessageLogPath':
                continue
            value = nodes[index + 1]
            if value.tag == 'map':
                children = list(value)
                for j, child in enumerate(children[:-1]):
                    if child.tag == 'key' and child.text == 'Value':
                        value = children[j + 1]
                        break
            if value.tag == 'string' and value.text and value.text.strip():
                paths.append(Path(os.path.expandvars(value.text.strip())).expanduser())
    return paths


def discover_folders(viewer, appdata=None):
    """Bounded search of viewer preferences and immediate avatar folders only."""
    from log_reader import eligible
    roaming = Path(appdata or os.environ.get('APPDATA', str(Path.home())))
    roots = [roaming / name for name in ROOTS.get(viewer, ())]
    roots = [path for path in roots if path.is_dir()]
    candidates = set()
    searched = set()

    def children(path):
        try:
            # No recursive disk scan, symlink traversal or chat-file reads.
            with os.scandir(path) as entries:
                result = []
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False) and entry.name not in {'user_settings', 'logs', 'cache', 'browser_profile'}:
                        result.append(Path(entry.path))
                        if len(result) >= 250:
                            break
                return result
        except OSError:
            return []

    def has_transcripts(path):
        try:
            with os.scandir(path) as entries:
                for count, entry in enumerate(entries):
                    if count >= 3000:
                        break
                    if entry.is_file(follow_symlinks=False) and (eligible(Path(entry.name)) or entry.name.casefold() == 'chat.txt'):
                        return True
        except OSError:
            pass
        return False

    def inspect(path):
        identity = os.path.normcase(os.path.abspath(path))
        if identity in searched:
            return
        searched.add(identity)
        if has_transcripts(path):
            candidates.add(path)
        for child in children(path):
            if has_transcripts(child):
                candidates.add(child)

    for root in roots:
        avatar_dirs = children(root)
        inspect(root)
        settings_dirs = [root / 'user_settings', root] + avatar_dirs
        for directory in settings_dirs:
            settings_files = [directory / name for name in ('settings.xml', 'settings_per_account.xml', 'settings_per_account_coolvlviewer.xml')]
            try:
                settings_files.extend(list(directory.glob('settings_coolvlviewer_*.xml'))[:20])
            except OSError:
                pass
            for settings_file in settings_files:
                for configured in _settings_log_paths(settings_file):
                    inspect(configured)
    return sorted(candidates, key=lambda path: str(path).casefold())
