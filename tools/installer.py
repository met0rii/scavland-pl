"""Scavland PL installer: builds patches locally; never downloads game files."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from tools.patch_core import GAME_FILES, PATCH_FILES, LOCALES, build_files, file_digest, read_json, require, safe_path

BACKUP = 'Scavland_Data/ScavlandPL-backup'

def encoded_json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def validate_payload(payload):
    require(payload.get('schema') == 1, 'Nieobsługiwany format moda.')
    config = payload['game']
    require(set(config['original_files']) == GAME_FILES, 'Nieprawidłowa lista plików.')
    require(len(payload['translations']) == 44 and sum(map(len, payload['translations'].values())) == 9980, 'Niekompletne tłumaczenie.')
    for rows in payload['translations'].values():
        require(len({r['id'] for r in rows}) == len(rows), 'Powtórzone identyfikatory.')
        require(all(set(r) == {'id', 'pl'} and isinstance(r['pl'], str) for r in rows), 'Nieprawidłowe teksty.')
    language = next(r for r in payload['translations']['DefaultTable'] if r['id'] == 754900687421440)
    require(language['pl'] == 'English', 'Nazwa języka musi pozostać English.')

@contextmanager
def workspace(game):
    parent = safe_path(game, 'Scavland_Data')
    folder = Path(tempfile.mkdtemp(prefix='.scavland-pl-', dir=parent)).resolve()
    require(folder.parent == parent.resolve(), 'Nieprawidłowy katalog tymczasowy.')
    try:
        yield folder
    finally:
        # The resolved deletion target must be the private temporary child created above.
        require(folder.parent == parent.resolve() and folder.name.startswith('.scavland-pl-'), 'Nieprawidłowa ścieżka sprzątania.')
        if folder.exists():
            shutil.rmtree(folder)

def inspect_game(game, payload):
    game = Path(game).resolve()
    require((game / 'Scavland.exe').is_file(), 'Wskaż folder zawierający Scavland.exe.')
    config = payload['game']
    originals = config['original_files']
    state_path = safe_path(game, BACKUP + '/state.json')
    backup = safe_path(game, BACKUP)
    if backup.exists():
        require(state_path.is_file(), 'Kopia moda jest niekompletna. Zachowaj ją i przywróć grę przez Steam.')
        state = read_json(state_path)
        require(state.get('schema') == 1 and state.get('steam_build_id') == config['steam_build_id'], 'Niezgodna kopia zapasowa moda.')
        require(set(state['current']) == set(PATCH_FILES), 'Nieprawidłowy stan instalacji.')
        sources = {name: safe_path(backup, 'files/' + name) for name in PATCH_FILES}
        for name, source in sources.items():
            require(source.is_file() and file_digest(source) == originals[name]['sha256'], 'Uszkodzona lokalna kopia: ' + name)
    else:
        state = {'schema': 1, 'steam_build_id': config['steam_build_id'], 'version': None, 'current': {name: originals[name]['sha256'] for name in PATCH_FILES}}
        sources = {name: safe_path(game, name) for name in PATCH_FILES}
    for name in GAME_FILES:
        path = safe_path(game, name)
        expected = originals[name]['sha256'] if name == LOCALES else state['current'][name]
        require(path.is_file() and file_digest(path) == expected,
                'Niezgodny plik: ' + name + '\nWymagana jest oryginalna wersja Steam Build ' + config['steam_build_id'] +
                '. Wcześniejsze paczki 1.0/1.1 usuń przez sprawdzenie spójności w Steam.')
    return sources, state, state_path

def commit_files(game, outputs, state_path, state):
    # Prepare rollback copies before replacing any installed file.
    with workspace(game) as work:
        prepared, rollback = {}, {}
        for index, (relative, source) in enumerate(outputs.items()):
            target = safe_path(game, relative)
            prepared[relative] = work / ('new-' + str(index))
            rollback[relative] = work / ('old-' + str(index))
            shutil.copy2(source, prepared[relative])
            shutil.copy2(target, rollback[relative])
        new_state = work / 'state.json'
        new_state.write_bytes(encoded_json(state))
        changed = []
        try:
            for relative in outputs:
                os.replace(prepared[relative], safe_path(game, relative))
                changed.append(relative)
            os.replace(new_state, state_path)
        except BaseException:
            for relative in reversed(changed):
                os.replace(rollback[relative], safe_path(game, relative))
            raise

def install(game, payload, progress=print):
    validate_payload(payload)
    game = Path(game).resolve()
    sources, previous, state_path = inspect_game(game, payload)
    config = payload['game']
    needed = sum(config['original_files'][name]['size'] for name in PATCH_FILES) * 5
    require(shutil.disk_usage(game).free > needed, 'Brakuje miejsca na przygotowanie plików i lokalną kopię (około 1 GB).')
    with workspace(game) as work:
        outputs = build_files(sources, payload['translations'], config, work / 'patched', progress)
        state = {**previous, 'version': payload['version'], 'current': {name: file_digest(path) for name, path in outputs.items()}}
        if not state_path.exists():
            staged_backup = work / 'backup'
            for relative, source in sources.items():
                target = safe_path(staged_backup, 'files/' + relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                require(file_digest(target) == config['original_files'][relative]['sha256'], 'Błąd zapisu kopii zapasowej.')
            (staged_backup / 'state.json').write_bytes(encoded_json(previous))
            backup = safe_path(game, BACKUP)
            require(not backup.exists(), 'Katalog kopii pojawił się podczas instalacji.')
            os.replace(staged_backup, backup)
        # Recheck current files in case another program changed them while building.
        inspect_game(game, payload)
        commit_files(game, outputs, state_path, state)
    inspect_game(game, payload)
    progress('Zainstalowano Scavland PL ' + payload['version'] + '. W grze wybierz English.')

def restore(game, payload, progress=print):
    validate_payload(payload)
    game = Path(game).resolve()
    sources, state, state_path = inspect_game(game, payload)
    if not state['version']:
        progress('Pliki gry są oryginalne.')
        return
    restored = {**state, 'version': None, 'current': {name: payload['game']['original_files'][name]['sha256'] for name in PATCH_FILES}}
    commit_files(game, sources, state_path, restored)
    inspect_game(game, payload)
    progress('Przywrócono oryginalne pliki. Lokalna kopia pozostaje w Scavland_Data/ScavlandPL-backup.')

def default_game():
    candidates = [Path.cwd(), Path(sys.executable).parent]
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                steam = Path(winreg.QueryValueEx(key, 'SteamPath')[0])
            candidates.append(steam / 'steamapps/common/Scavland')
        except OSError:
            pass
        candidates.append(Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Steam/steamapps/common/Scavland')
    return next((p for p in candidates if (p / 'Scavland.exe').is_file()), None)

def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['install', 'check', 'restore'])
    parser.add_argument('--game', type=Path)
    parser.add_argument('--payload', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    embedded = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'mod.json'
    payload = read_json(args.payload or embedded)
    validate_payload(payload)
    if args.self_test:
        import UnityPy
        import lz4.block
        data = b'Scavland PL runtime check' * 100
        require(lz4.block.decompress(lz4.block.compress(data)) == data, 'Błąd biblioteki kompresji.')
        print('PASS: ' + payload['version'] + ', 9980 tekstów, UnityPy ' + UnityPy.__version__)
        return
    interactive = args.action is None
    try:
        action = args.action
        game = args.game
        if interactive:
            print('Scavland PL ' + payload['version'])
            print('Mod zastępuje English. Zamknij grę przed instalacją lub przywracaniem.')
            print('1 - Zainstaluj / aktualizuj\n2 - Sprawdź pliki\n3 - Przywróć oryginały\n0 - Zakończ')
            choice = input('Wybierz: ').strip()
            if choice == '0':
                return
            require(choice in ('1', '2', '3'), 'Nieprawidłowy wybór.')
            action = {'1': 'install', '2': 'check', '3': 'restore'}[choice]
            suggested = default_game()
            print('Folder gry' + (': ' + str(suggested) if suggested else ' zawierający Scavland.exe'))
            selected = input('Wpisz ścieżkę' + (' lub naciśnij Enter' if suggested else '') + ': ').strip().strip('"')
            game = Path(selected) if selected else suggested
        require(game is not None, 'Podaj folder gry przez --game.')
        if action == 'install':
            install(game, payload)
        elif action == 'restore':
            restore(game, payload)
        else:
            _, state, _ = inspect_game(game, payload)
            print('Pliki poprawne. ' + ('Spolszczenie ' + state['version'] + '; wybierz English.' if state['version'] else 'Oryginalna gra.'))
    except (OSError, ValueError, KeyError) as error:
        print('BŁĄD: ' + str(error), file=sys.stderr)
        if not interactive:
            raise SystemExit(1)
    finally:
        if interactive:
            input('Naciśnij Enter, aby zamknąć.')

if __name__ == '__main__':
    main()
