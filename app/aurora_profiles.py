"""Aurora's documented account/grid transcript layout (read-only).

Reference: Aurora-Viewer/Aurora-Viewer, world/chat_log/{names,store}.rs,
settings.rs and login_accounts.rs. No credentials or chat contents are read.
"""
import json
import os
from pathlib import Path
from uuid import UUID

ROOT = Path('Aurora') / 'AuroraViewer' / 'config'


def config_dir(appdata=None):
    return Path(appdata or os.environ.get('APPDATA', str(Path.home()))) / ROOT


def _json(path):
    try:
        if path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
            return None
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError, RecursionError):
        return None


def _account_id(value):
    try:
        agent = UUID(str(value))
        return str(agent) if agent.int else None
    except ValueError:
        return None


def account_names(appdata=None):
    """Only the public avatar name and UUID from Aurora's login catalogue."""
    entries = _json(config_dir(appdata) / 'login_accounts.json')
    names = {}
    ambiguous = set()
    if isinstance(entries, list):
        for entry in entries[:250]:
            if not isinstance(entry, dict):
                continue
            agent = _account_id(entry.get('agent'))
            username = entry.get('username')
            if agent and agent not in ambiguous and isinstance(username, str) and username.strip():
                name = username.strip()
                # An ambiguous catalogue entry must not select a different avatar.
                if agent in names and names[agent] != name:
                    names.pop(agent)
                    ambiguous.add(agent)
                else:
                    names[agent] = name
    return names


def folder_account(folder, appdata=None):
    folder = Path(folder)
    if folder.parent.name.casefold() != 'chat_logs':
        return ''
    agent = _account_id(folder.parent.parent.name)
    return account_names(appdata).get(agent, '') if agent else ''


def folder_label(folder):
    name = folder_account(folder)
    return f'{name} · {Path(folder).name} — {folder}' if name else str(folder)


def _directories(folder):
    try:
        with os.scandir(folder) as entries:
            result = []
            for count, entry in enumerate(entries):
                if count >= 1000 or len(result) >= 250:
                    break
                if entry.is_dir(follow_symlinks=False):
                    result.append(Path(entry.path))
            return result
    except OSError:
        return []


def discover_folders(appdata=None):
    """Bounded traversal: accounts / UUID / chat_logs / grid, never recursively."""
    from log_reader import eligible
    config = config_dir(appdata)
    settings = _json(config / 'settings.json')
    location = settings.get('chat_log_location') if isinstance(settings, dict) else None
    # Aurora's preference holds an accounts root, not a transcript folder.
    root = Path(os.path.expandvars(location.strip())).expanduser() if isinstance(location, str) and location.strip() else config / 'accounts'
    if not root.is_absolute() or root.is_symlink():
        return []
    found = []
    for account in _directories(root):
        logs = account / 'chat_logs'
        if not _account_id(account.name) or logs.is_symlink():
            continue
        for grid in _directories(logs):
            try:
                with os.scandir(grid) as entries:
                    for count, entry in enumerate(entries):
                        if count >= 3000:
                            break
                        if entry.is_file(follow_symlinks=False) and (eligible(Path(entry.name)) or entry.name.casefold() == 'chat.txt'):
                            found.append(grid)
                            break
            except OSError:
                pass
    return sorted(set(found), key=lambda path: str(path).casefold())
