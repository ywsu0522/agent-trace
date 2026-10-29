"""Explicit, independent corpus loading and verified optional email setup."""

import gzip
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
from urllib.request import urlopen

from agent_trace.paths import asset_root


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


class Corpus:
    def __init__(self, docs_dir, emails_path):
        self.docs_dir = Path(docs_dir)
        self.emails_path = Path(emails_path)
        self._emails = None

    def docs(self):
        paths = sorted(self.docs_dir.glob('*.md'))
        if not paths:
            raise FileNotFoundError(f'No documents in {self.docs_dir}')
        docs = []
        for path in paths:
            text = path.read_text(encoding='utf-8')
            title = next((line[2:].strip() for line in text.splitlines() if line.startswith('# ')), path.stem)
            docs.append({'doc_id': path.stem, 'title': title, 'text': text})
        return docs

    def emails(self):
        if self._emails is None:
            if not self.emails_path.is_file():
                raise FileNotFoundError('Email corpus missing. Run prepare-data or supply --emails PATH; do not silently substitute a smaller corpus.')
            with self.emails_path.open(encoding='utf-8') as stream:
                self._emails = [json.loads(line) for line in stream if line.strip()]
        return self._emails

    def emails_on(self, date):
        return [email for email in self.emails() if email['date'][:10] == date]


def prepare_email(destination, archive=None, download=False):
    spec = json.loads((asset_root() / 'datasets/email-source.json').read_text(encoding='utf-8'))
    destination = Path(destination).resolve()
    sidecar = destination.with_suffix('.provenance.json')
    if destination.exists():
        if (sidecar.exists() and json.loads(sidecar.read_text(encoding='utf-8')).get('uncompressed_sha256')
                == file_hash(destination) == spec['uncompressed_sha256']):
            return json.loads(sidecar.read_text(encoding='utf-8'))
        raise FileExistsError(f'{destination} already exists without matching provenance; choose another destination')
    if archive is None and not download:
        raise ValueError('Provide --archive PATH or explicitly use --download')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_archive = None
    if archive is None:
        with NamedTemporaryFile(dir=destination.parent, suffix='.gz', delete=False) as stream:
            temporary_archive = Path(stream.name)
            with urlopen(spec['url'], timeout=60) as response:
                shutil.copyfileobj(response, stream)
        archive = temporary_archive
    archive = Path(archive)
    try:
        if archive.stat().st_size != spec['bytes'] or file_hash(archive) != spec['sha256']:
            raise ValueError('Archive does not match the historical corpus checksum')
        with NamedTemporaryFile(dir=destination.parent, suffix='.jsonl', delete=False) as stream:
            temporary_output = Path(stream.name)
            try:
                with gzip.open(archive, 'rb') as source:
                    shutil.copyfileobj(source, stream)
            except BaseException:
                stream.close()
                temporary_output.unlink(missing_ok=True)
                raise
        count = 0
        with temporary_output.open(encoding='utf-8') as stream:
            for line in stream:
                if line.strip():
                    json.loads(line)
                    count += 1
        if count != spec['emails']:
            temporary_output.unlink(missing_ok=True)
            raise ValueError('Email count does not match the corpus manifest')
        if file_hash(temporary_output) != spec['uncompressed_sha256']:
            temporary_output.unlink(missing_ok=True)
            raise ValueError('Uncompressed email corpus checksum mismatch')
        temporary_output.replace(destination)
        result = {**spec, 'uncompressed_sha256': file_hash(destination), 'email_count': count}
        sidecar.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        return result
    finally:
        if temporary_archive:
            temporary_archive.unlink(missing_ok=True)
