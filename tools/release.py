"""Validate translations and package a local patch installer without game assets."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
README_NAME = 'Scavland-PL-CZYTAJ-MNIE.txt'
TAG = re.compile(r'</?[A-Za-z][^<>]*>')
PLACEHOLDER = re.compile(r'\{[^{}]*\}')
VERSION_RE = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?\Z')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def digest(data):
    return hashlib.sha256(data).hexdigest()

def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def release_version(base, run_number=None, run_attempt=None):
    require(bool(VERSION_RE.fullmatch(base)), 'Invalid VERSION; expected e.g. 1.1.0')
    if run_number is None:
        return base
    require('-' not in base, 'CI base version must be major.minor.patch')
    require(str(run_number).isdigit() and int(run_number) > 0, 'Invalid run number')
    attempt = str(run_attempt or '1')
    require(attempt.isdigit() and int(attempt) > 0, 'Invalid run attempt')
    return f'{base}-ci.{int(run_number)}.{int(attempt)}'

def validate_entries(name, entries, source):
    require(isinstance(entries, list) and len(entries) == len(source), f'{name}: missing/extra entries')
    require(len({e['id'] for e in entries}) == len(entries), f'{name}: duplicate IDs')
    for entry, original in zip(entries, source):
        label = f'{name}/{original["id"]}'
        require(all(entry.get(k) == original[k] for k in ('id', 'key', 'en')), f'{label}: source changed')
        en, pl = original['en'], entry.get('pl')
        if name == 'DefaultTable' and entry['key'] == 'Menu.Language_Name':
            require(pl == 'English', 'The language selector must keep the English label')
        require(isinstance(pl, str) and bool(pl or not en), f'{label}: missing Polish text')
        require(not any(0xD800 <= ord(c) <= 0xDFFF or c == '\ufffd' for c in pl), f'{label}: invalid Unicode')
        for pattern in (PLACEHOLDER, TAG):
            require(Counter(pattern.findall(en)) == Counter(pattern.findall(pl)), f'{label}: placeholders/tags changed')
        require(en.count('\n') == pl.count('\n'), f'{label}: line breaks changed')
        if en.startswith('< ') and en.rstrip().endswith(' >'):
            require(pl.startswith('< ') and pl.rstrip().endswith(' >'), f'{label}: speech delimiters changed')
    return {'covered': len(entries), 'changed': sum(e['en'] != e['pl'] for e in entries)}

def validate_translations(root=ROOT):
    source_manifest = read_json(root / 'source/manifest.json')
    names = {t['table'] for t in source_manifest['tables']}
    paths = {p.name.removesuffix('.pl.json'): p for p in (root / 'translation').glob('*.pl.json')}
    require(set(paths) == names, 'Translation tables do not match the source manifest')
    translations, counts = {}, {}
    for name in sorted(names):
        entries = read_json(paths[name])
        source = read_json(root / 'source' / (name + '.json'))
        counts[name] = validate_entries(name, entries, source)
        require(len(source) == next(t['entries'] for t in source_manifest['tables'] if t['table'] == name), f'{name}: source count changed')
        translations[name] = entries
    return translations, counts

def render(root, name, version):
    return (root / 'docs' / name).read_text(encoding='utf-8').replace('{{VERSION}}', version)

def write_zip(path, payload):
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 11, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data, compresslevel=9)
    with zipfile.ZipFile(path) as archive:
        require(len(archive.namelist()) == len(payload) and set(archive.namelist()) == set(payload), 'ZIP file list mismatch')
        for name, data in payload.items():
            require(digest(archive.read(name)) == digest(data), f'ZIP readback mismatch: {name}')


def build(root, out, version):
    from tools.build_distribution import freeze, licenses_text, make_payload
    release_version(version)
    translations, counts = validate_translations(root)
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    payload = make_payload(root, version, translations)
    exe, audit = freeze(root, out / '.build', payload)
    files = {
        'Scavland-PL-Instalator.exe': exe.read_bytes(),
        README_NAME: render(root, 'INSTALL.txt', version).replace('\n', '\r\n').encode('utf-8-sig'),
        'LICENCJE.txt': licenses_text().encode('utf-8-sig'),
    }
    zip_path = out / f'Scavland-Polish-Translation-{version}.zip'
    write_zip(zip_path, files)
    checksum = file_digest(zip_path)
    (out / 'SHA256SUMS').write_text(f'{checksum}  {zip_path.name}\n', encoding='ascii')
    (out / 'OPIS-NEXUS.txt').write_text(render(root, 'NEXUS.txt', version), encoding='utf-8-sig')
    (out / 'release-notes.md').write_text(render(root, 'RELEASE.md', version), encoding='utf-8')
    report = {'result': 'PASS', 'version': version, 'steam_build_id': payload['game']['steam_build_id'],
              'covered_entries': sum(t['covered'] for t in counts.values()), 'tables': len(counts),
              'archive': zip_path.name, 'archive_sha256': checksum, 'archive_bytes': zip_path.stat().st_size,
              'zip_files': sorted(files), 'game_archives_in_package': False, 'game_required_for_build': False,
              'font_patch_inserted_bytes': len(bytes.fromhex(payload['game']['font_patch']['insert_hex'])),
              'installer_audit': audit, 'language_selection': 'English', 'runtime_game_test': 'not performed'}
    write_json(out / 'validation.json', report)
    print(f'PASS: {report["covered_entries"]} entries, {len(counts)} tables; no game archives in ZIP')
    print(zip_path)
    return report

def publish(out, version):
    import subprocess
    release_version(version)
    repo, commit = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_SHA']
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo), 'Invalid repository')
    require(re.fullmatch(r'[a-fA-F0-9]{40}', commit), 'Invalid commit')
    archive = out / f'Scavland-Polish-Translation-{version}.zip'
    require(archive.is_file(), 'Missing release package')
    subprocess.run(['gh', 'release', 'create', 'v' + version, str(archive), str(out / 'SHA256SUMS'),
                    '--repo', repo, '--target', commit, '--title', 'Scavland PL ' + version,
                    '--notes-file', str(out / 'release-notes.md'), '--prerelease', '--latest=false'], check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate')
    sub.add_parser('version')
    p = sub.add_parser('build')
    p.add_argument('--out', type=Path, default=ROOT / 'dist')
    p.add_argument('--version', default=None)
    p = sub.add_parser('publish')
    p.add_argument('--out', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if args.command == 'validate':
        _, counts = validate_translations()
        print(f'PASS: {sum(t["covered"] for t in counts.values())} entries in {len(counts)} tables')
    elif args.command == 'version':
        version = release_version((ROOT / 'VERSION').read_text().strip(), os.environ.get('GITHUB_RUN_NUMBER'), os.environ.get('GITHUB_RUN_ATTEMPT'))
        print(version)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
                stream.write(f'version={version}\n')
    elif args.command == 'publish':
        publish(args.out, os.environ['RELEASE_VERSION'])
    else:
        version = args.version or (ROOT / 'VERSION').read_text().strip()
        build(ROOT, args.out, version)

if __name__ == '__main__':
    # Direct execution and PyInstaller entry points both need the project package root.
    sys.path.insert(0, str(ROOT))
    try:
        main()
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        raise SystemExit(f'ERROR: {error}')
