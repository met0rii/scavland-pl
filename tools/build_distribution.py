"""Freeze the installer and package only code, translations and tiny patch metadata."""
from __future__ import annotations
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from tools.installer import validate_payload
from tools.patch_core import read_json

def make_payload(root, version, translations):
    payload = {
        'schema': 1, 'version': version,
        'game': read_json(root / 'config/game-build.json'),
        'translations': {name: [{'id': int(e['id']), 'pl': e['pl']} for e in rows] for name, rows in translations.items()},
    }
    validate_payload(payload)
    return payload

def licenses_text():
    sections = ['Licencje dołączonych narzędzi i bibliotek. Zasoby Scavland nie są dołączane.\n']
    for distribution in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
        files = [p for p in (distribution.files or []) if any(word in p.name.lower() for word in ('license', 'copying')) and p.suffix.lower() in ('', '.txt', '.md', '.rst')]
        for path in sorted(files):
            source = Path(distribution.locate_file(path))
            if source.is_file():
                sections.append('\n=== ' + distribution.metadata['Name'] + ' ' + distribution.version + ' / ' + path.name + ' ===\n')
                sections.append(source.read_text(encoding='utf-8', errors='replace'))
    for name in ('LICENSE.txt', 'LICENSE'):
        source = Path(sys.base_prefix) / name
        if source.is_file():
            sections.append('\n=== Python ===\n' + source.read_text(encoding='utf-8', errors='replace'))
            break
    return '\n'.join(sections)

def freeze(root, work, payload):
    if os.name != 'nt':
        raise ValueError('Instalator Windows należy budować na Windows.')
    from PyInstaller.archive.readers import CArchiveReader
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    (work / 'mod.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    log_path = work / 'pyinstaller.log'
    command = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--console',
        '--name', 'Scavland-PL-Instalator', '--paths', str(root),
        '--distpath', str(work / 'bin'), '--workpath', str(work / 'temp'), '--specpath', str(work),
        '--add-data', str(work / 'mod.json') + ':.',
        '--collect-data', 'UnityPy',
        str(root / 'tools/installer.py'),
    ]
    print('Budowanie samodzielnego instalatora Windows…', flush=True)
    with log_path.open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError('PyInstaller nie zbudował instalatora.\n' + log_path.read_text(encoding='utf-8')[-6000:])
    exe = work / 'bin/Scavland-PL-Instalator.exe'
    entries = CArchiveReader(str(exe)).toc
    forbidden = [name for name in entries if name.lower().endswith(('.bundle', '.unity3d', '.assets', '.font')) or any(part in name.replace('\\', '/').lower().split('/') for part in ('backup', 'source', 'translation', 'publish'))]
    if forbidden:
        raise ValueError('Niedozwolone zasoby w instalatorze: ' + str(forbidden))
    if 'mod.json' not in entries:
        raise ValueError('Brak tłumaczenia w instalatorze.')
    subprocess.run([str(exe), '--self-test'], check=True)
    return exe, {'embedded_entries': len(entries), 'forbidden_game_asset_entries': forbidden, 'embedded_payload_bytes': (work / 'mod.json').stat().st_size}
