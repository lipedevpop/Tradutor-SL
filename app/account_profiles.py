"""Preferred log accounts; this does not log in to a viewer."""
from pathlib import Path
import re
import unicodedata

AUTO_ACCOUNT = 'Automática'
PREFERRED_ACCOUNTS = ('lipe.vortex', 'mab.leeeroy')
ACCOUNT_CHOICES = (AUTO_ACCOUNT,) + PREFERRED_ACCOUNTS


def account_for_folder(path):
    from aurora_profiles import folder_account
    name = folder_account(path) or Path(path).name
    name = unicodedata.normalize('NFKC', name).casefold().strip()
    name = re.sub(r'[._\s]+', '.', name)
    name = re.sub(r'\.resident$', '', name)
    return name if name in PREFERRED_ACCOUNTS else None


def account_folders(paths, choice=AUTO_ACCOUNT):
    """Exact account matching only; never guess if both preferred accounts exist."""
    if choice in PREFERRED_ACCOUNTS:
        return [path for path in paths if account_for_folder(path) == choice]
    preferred = [path for path in paths if account_for_folder(path) in PREFERRED_ACCOUNTS]
    return preferred or list(paths)
