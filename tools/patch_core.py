"""Apply translation data to the player's verified installation. Contains no game assets."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import struct
import zlib

AA = 'Scavland_Data/StreamingAssets/aa/'
EN = AA + 'StandaloneWindows64/localization-string-tables-english(en)_assets_all.bundle'
LOCALES = AA + 'StandaloneWindows64/localization-locales_assets_all.bundle'
CATALOG = AA + 'catalog.bin'
FONT = 'Scavland_Data/data.unity3d'
PATCH_FILES = (EN, CATALOG, FONT)
GAME_FILES = set(PATCH_FILES) | {LOCALES}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def safe_path(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    require(not rel.is_absolute() and '..' not in rel.parts, 'Niedozwolona ścieżka pliku.')
    target = root / rel
    require(target.resolve().is_relative_to(root) and target.resolve() != root, 'Plik wychodzi poza folder gry.')
    current = target
    while current != root:
        require(not current.is_symlink(), 'Dowiązania w ścieżkach plików moda nie są obsługiwane.')
        current = current.parent
    return target

def apply_splice(data, recipe):
    require(digest(data) == recipe['original_object_sha256'], 'Niezgodny obiekt czcionki.')
    offset = recipe['offset']
    old, new = bytes.fromhex(recipe['remove_hex']), bytes.fromhex(recipe['insert_hex'])
    require(0 <= offset <= len(data) and data[offset:offset + len(old)] == old, 'Niezgodne miejsce poprawki czcionki.')
    result = data[:offset] + new + data[offset + len(old):]
    require(digest(result) == recipe['patched_object_sha256'], 'Błąd weryfikacji poprawki czcionki.')
    return result

def update_catalog(data, old_crc, old_size, new_crc, new_size):
    marker = struct.pack('<II', old_crc, old_size)
    require(data.count(marker) == 1, 'Niejednoznaczny wpis CRC w katalogu gry.')
    offset = data.index(marker)
    require(EN.rsplit('/', 1)[-1].encode('ascii') in data[max(0, offset - 400):offset], 'Nieprawidłowy wpis katalogu.')
    return data[:offset] + struct.pack('<II', new_crc, new_size) + data[offset + 8:]

def build_files(sources, translations, config, destination, progress=print):
    import UnityPy
    destination = Path(destination)
    progress('Przygotowuję polskie teksty…')
    english_bytes = Path(sources[EN]).read_bytes()
    env = UnityPy.load(english_bytes)
    require(len(env.file.files) == 1, 'Nieobsługiwany układ paczki językowej.')
    old_crc = zlib.crc32(next(iter(env.file.files.values())).reader.bytes)
    expected, seen = {}, set()
    for obj in env.objects:
        tree = obj.read_typetree()
        name = tree.get('m_Name', '').removesuffix('_en')
        if name in translations:
            require(name not in seen, 'Powtórzona tabela: ' + name)
            seen.add(name)
            values = {int(e['id']): e['pl'] for e in translations[name]}
            require(set(values) == {e['m_Id'] for e in tree['m_TableData']}, 'Niezgodna tabela: ' + name)
            for entry in tree['m_TableData']:
                entry['m_Localized'] = values[entry['m_Id']]
            obj.save_typetree(tree)
        expected[obj.path_id] = copy.deepcopy(tree)
    require(seen == set(translations), 'Nie zapisano wszystkich tabel.')
    encoded = env.file.save(packer='lz4')
    after = UnityPy.load(encoded)
    require({o.path_id: o.read_typetree() for o in after.objects} == expected, 'Błąd odczytu polskich tekstów.')
    new_crc = zlib.crc32(next(iter(after.file.files.values())).reader.bytes)
    outputs = {}
    for relative, data in (
        (EN, encoded),
        (CATALOG, update_catalog(Path(sources[CATALOG]).read_bytes(), old_crc, len(english_bytes), new_crc, len(encoded))),
    ):
        target = safe_path(destination, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        outputs[relative] = target
    del env, after, expected, encoded
    progress('Dodaję obsługę polskich liter do lokalnego pliku gry…')
    env = UnityPy.load(Path(sources[FONT]).read_bytes())
    recipe = config['font_patch']
    targets = [o for o in env.objects if o.assets_file.name == recipe['asset'] and o.path_id == recipe['path_id']]
    require(len(targets) == 1, 'Nie znaleziono właściwej czcionki.')
    targets[0].set_raw_data(apply_splice(targets[0].get_raw_data(), recipe))
    target = safe_path(destination, FONT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(env.file.save(packer='original'))
    require(file_digest(target) == config['font_patched_sha256'], 'Wynik poprawki czcionki różni się od sprawdzonego pliku.')
    outputs[FONT] = target
    progress('Wszystkie przygotowane pliki przeszły weryfikację.')
    return outputs
