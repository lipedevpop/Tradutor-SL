"""Read-only, incremental reader for SL viewer conversation transcripts."""
from dataclasses import dataclass
from pathlib import Path
import os
import re
import unicodedata

# SL viewers may omit date/seconds or add a time zone (Cool VL: PST/PDT).
# Preserve the complete timestamp for display; no time conversion is needed.
TIME_ZONE = r'(?:[A-Z]{2,6}(?:[+-]\d{1,2}(?::?\d{2})?)?|[+-]\d{2}:?\d{2})'
LINE = re.compile(
    r"^(?:\[((?:[^\]\r\n]{1,40}\s+)?\d{1,2}:\d{2}(?::\d{2})?"
    r"(?:\s+[AP]M)?(?:\s+" + TIME_ZONE + r")?)\]\s*)?([^:\[\]\r\n]+):\s?(.*)$",
    re.IGNORECASE)


def normalized(value):
    value = unicodedata.normalize('NFKC', value).casefold().strip()
    value = re.sub(r'[._\s]+', ' ', value)
    return re.sub(r'\s+resident$', '', value)


@dataclass
class Message:
    conversation: str
    timestamp: str
    sender: str
    text: str


def parse_line(line, conversation, aliases=(), normalized_aliases=None):
    line = line.lstrip('\ufeff')
    if line.startswith((' ', '\t')):
        return None  # Indented continuation lines are not separate IMs.
    match = LINE.match(line)
    if not match:
        return None
    stamp, sender, body = match.groups()
    identities = {normalized(sender)}
    account = re.search(r'\(([^()]+)\)\s*$', sender)
    if account:
        identities.add(normalized(account.group(1)))
        identities.add(normalized(sender[:account.start()]))
    if identities.intersection({'second life', 'system', 'you', 'você', 'voce'}):
        return None
    alias_identities = normalized_aliases
    if alias_identities is None:
        alias_identities = {normalized(x) for x in aliases if x.strip()}
    if identities.intersection(alias_identities):
        return None
    if not individual_sender(sender, conversation):
        return None
    body = body.strip()
    if not body or not any(c.isalpha() for c in body):
        return None
    if re.fullmatch(r'(?:https?://|secondlife://)\S+', body, re.I):
        return None
    return Message(conversation, stamp or '—', sender, body)


def peer_name(conversation):
    # Alchemy can append a monthly/daily suffix when date-stamped logs are enabled.
    return re.sub(r'-\d{4}-\d{2}(?:-\d{2})?$', '', conversation)


def eligible(path):
    name = peer_name(path.stem).casefold()
    # Only account-shaped transcript names. Group/conference names are excluded
    # before their files are opened, including Alchemy's explicit (group) suffix.
    if path.suffix.casefold() != '.txt':
        return False
    if any(marker in name for marker in ('(group)', '(grupo)', 'conference', 'conferencia', 'conferência', 'ad-hoc')):
        return False
    if name in {'chat', 'conversation', 'conversation.log', 'debug', 'system', 'second life', 'object', 'objects', 'nearby', 'local'}:
        return False
    return bool(re.fullmatch(r'[a-z0-9]+(?:[._ ][a-z0-9]+)?',name))


def individual_sender(sender, conversation):
    if not eligible(Path(conversation + '.txt')):
        return False
    account = re.search(r'\(([^()]+)\)\s*$',sender)
    # When an account name is present, never substitute the display name for it.
    identity = account.group(1) if account else sender
    if not re.fullmatch(r'[A-Za-z0-9]+(?:[._ ][A-Za-z0-9]+)?',identity.strip()):
        return False
    return normalized(identity) == normalized(peer_name(conversation))


class LogReader:
    """Existing files start at EOF; new files are read from their beginning.

    Files are opened in binary mode to preserve offsets and partial UTF-8
    sequences. Only complete lines are parsed; transcripts are never modified.
    """
    def __init__(self, folder, aliases=()):
        self.folder = Path(folder)
        if not self.folder.is_dir():
            raise ValueError('Selecione a pasta do avatar que contém os arquivos .txt.')
        self.aliases = tuple(aliases)
        # Aliases are compared for every line, so normalize them once per reader.
        self.normalized_aliases = {normalized(value) for value in aliases if value.strip()}
        self.states = {}
        self.errors = []
        for path, stat in self.files():
            self.states[path] = (stat.st_size, b'', stat.st_ino, self._tail(path, stat.st_size))

    @staticmethod
    def _tail(path, offset, size=64):
        """Fingerprint bytes immediately before an offset.

        Some Windows filesystems report an unusable inode.  This small check
        catches an atomic log replacement even when the new file is larger.
        """
        if not offset:
            return b''
        try:
            with path.open('rb') as file:
                file.seek(max(0, offset - size))
                return file.read(min(size, offset))
        except OSError:
            return b''

    def files(self):
        # DirEntry metadata avoids a separate Windows stat call per file.
        with os.scandir(self.folder) as entries:
            for entry in entries:
                if not entry.name.casefold().endswith('.txt'):
                    continue
                path = Path(entry.path)
                if not eligible(path):
                    continue
                try:
                    if entry.is_file(follow_symlinks=False):
                        yield path, entry.stat(follow_symlinks=False)
                except OSError:
                    self.errors.append('Uma conversa está indisponível; nova tentativa em instantes.')

    def poll(self):
        messages = []
        self.errors = []
        if not self.folder.is_dir():
            raise OSError('A pasta das conversas não está disponível.')
        present = set()
        for path, stat in self.files():
            present.add(path)
            try:
                offset, pending, inode, fingerprint = self.states.get(
                    path, (0, b'', stat.st_ino, b''))
                replaced = (stat.st_ino != inode or
                            (offset and self._tail(path, offset) != fingerprint))
                if stat.st_size < offset or replaced:
                    offset, pending = 0, b''
                if stat.st_size == offset:
                    continue
                with path.open('rb') as file:
                    file.seek(offset)
                    chunk = file.read(256 * 1024)
                    offset = file.tell()
                lines = (pending + chunk).split(b'\n')
                pending = lines.pop()
                if len(pending) > 128 * 1024:
                    pending = b''
                    self.errors.append('Uma linha excessivamente longa foi ignorada.')
                self.states[path] = (offset, pending, stat.st_ino,
                                     self._tail(path, offset))
                for raw in lines:
                    msg = parse_line(raw.decode('utf-8', errors='replace').rstrip('\r'),
                                     path.stem, self.aliases, self.normalized_aliases)
                    if msg:
                        messages.append(msg)
            except OSError:
                self.errors.append('Não foi possível ler uma conversa; nova tentativa em instantes.')
        for missing in set(self.states) - present:
            del self.states[missing]
        return messages
