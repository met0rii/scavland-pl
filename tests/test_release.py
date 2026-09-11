import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from tools import release as r

class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.source = [{'id': '1', 'key': 'greeting', 'en': '<i>Hello {name}</i>\nBye'}]
        self.entries = [{**self.source[0], 'pl': '<i>Cześć {name}</i>\nPa'}]
    def check(self):
        return r.validate_entries('test', self.entries, self.source)
    def test_valid_polish_text(self):
        self.assertEqual(self.check()['covered'], 1)
    def test_all_project_tables(self):
        _, tables = r.validate_translations()
        self.assertEqual(len(tables), 44)
        self.assertEqual(sum(t['covered'] for t in tables.values()), 9980)
    def test_misleading_language_label_rejected(self):
        source=[{'id':'1','key':'Menu.Language_Name','en':'English'}]
        entries=[{**source[0],'pl':'Polski (test)'}]
        with self.assertRaisesRegex(ValueError, 'English label'):
            r.validate_entries('DefaultTable',entries,source)
        entries[0]['pl']='English'
        self.assertEqual(r.validate_entries('DefaultTable',entries,source)['covered'],1)
    def test_missing_entry_rejected(self):
        self.entries.clear()
        with self.assertRaisesRegex(ValueError, 'missing/extra'): self.check()
    def test_changed_identity_rejected(self):
        for key in ('id', 'key', 'en'):
            with self.subTest(key=key):
                original=self.entries[0][key]; self.entries[0][key]='changed'
                with self.assertRaisesRegex(ValueError, 'source changed'): self.check()
                self.entries[0][key]=original
    def test_duplicate_ids_rejected(self):
        self.source.append({'id':'2','key':'x','en':'x'})
        self.entries.append(copy.deepcopy(self.entries[0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'): self.check()
    def test_placeholder_and_tag_counts(self):
        for text in ('Cześć {name}\nPa', '<i>Cześć {other}</i>\nPa', '<i>Cześć {name} {name}</i>\nPa'):
            self.entries[0]['pl']=text
            with self.assertRaisesRegex(ValueError, 'placeholders/tags'): self.check()
    def test_newline_change_rejected(self):
        self.entries[0]['pl']='<i>Cześć {name}</i> Pa'
        with self.assertRaisesRegex(ValueError, 'line breaks'): self.check()
    def test_bad_unicode_rejected(self):
        self.entries[0]['pl']+="\ufffd"
        with self.assertRaisesRegex(ValueError, 'Unicode'): self.check()
    def test_empty_original_allowed(self):
        self.source=[{'id':'1','key':'empty','en':''}]
        self.entries=[{**self.source[0],'pl':''}]
        self.assertEqual(self.check()['changed'],0)
    def test_empty_translation_rejected(self):
        self.entries[0]['pl']=''
        with self.assertRaisesRegex(ValueError, 'missing Polish'):self.check()
    def test_legacy_speech_delimiter(self):
        self.source=[{'id':'1','key':'voice','en':'< Hello >'}]
        self.entries=[{**self.source[0],'pl':'Cześć'}]
        with self.assertRaisesRegex(ValueError, 'speech delimiters'):self.check()

class VersionTests(unittest.TestCase):
    def test_local_and_ci_versions(self):
        self.assertEqual(r.release_version('1.1.0'),'1.1.0')
        self.assertEqual(r.release_version('1.1.0','12','1'),'1.1.0-ci.12.1')
        self.assertNotEqual(r.release_version('1.1.0','12','1'),r.release_version('1.1.0','12','2'))
    def test_unsafe_or_invalid_versions(self):
        for value in ('../x','1.0;echo x','01.1.0','1.0','1.0.0\n','1.0.0/foo'):
            with self.subTest(value=value), self.assertRaises(ValueError):r.release_version(value)
        with self.assertRaises(ValueError):r.release_version('1.1.0','nope','1')

class ArchiveTests(unittest.TestCase):
    def test_repeatable_zip_and_unicode_readme(self):
        with tempfile.TemporaryDirectory(prefix='scavland-test-') as tmp:
            a,b=Path(tmp)/'a.zip',Path(tmp)/'b.zip'
            payload={'Scavland_Data/a.bin':b'123',r.README_NAME:'English → polski'.encode()}
            r.write_zip(a,payload);r.write_zip(b,payload)
            self.assertEqual(a.read_bytes(),b.read_bytes())

class FontPatchTests(unittest.TestCase):
    def test_tiny_splice_requires_exact_source_and_result(self):
        from tools.patch_core import apply_splice
        old=b'prefix-tail';new=b'prefix-123-tail'
        recipe={'original_object_sha256':r.digest(old),'patched_object_sha256':r.digest(new),'offset':7,'remove_hex':'','insert_hex':b'123-'.hex()}
        self.assertEqual(apply_splice(old,recipe),new)
        with self.assertRaises(ValueError):apply_splice(old+b'changed',recipe)
        recipe['insert_hex']='ff'
        with self.assertRaises(ValueError):apply_splice(old,recipe)

class InstallerTests(unittest.TestCase):
    def test_payload_contains_translations_without_original_assets(self):
        from tools.build_distribution import make_payload
        from tools.installer import validate_payload
        translations,_=r.validate_translations()
        payload=make_payload(r.ROOT,'1.2.0',translations)
        self.assertEqual(sum(map(len,payload['translations'].values())),9980)
        self.assertTrue(all(set(e)=={'id','pl'} for rows in payload['translations'].values() for e in rows))
        self.assertEqual(len(bytes.fromhex(payload['game']['font_patch']['insert_hex'])),12)
        payload['translations']['UI'].pop()
        with self.assertRaises(ValueError):validate_payload(payload)

    def test_path_escape_rejected(self):
        from tools.patch_core import safe_path
        with tempfile.TemporaryDirectory(prefix='scavland-unit-') as tmp:
            root=Path(tmp)
            self.assertEqual(safe_path(root,'Scavland_Data/test'),root.resolve()/'Scavland_Data/test')
            with self.assertRaises(ValueError):safe_path(root,'../escape')
            with self.assertRaises(ValueError):safe_path(root, str(root.parent/'escape'))

    def test_failed_replacement_restores_files_and_preserves_state(self):
        from tools.installer import commit_files
        from unittest.mock import patch
        import os
        with tempfile.TemporaryDirectory(prefix='scavland-unit-') as tmp:
            root=Path(tmp);(root/'Scavland_Data').mkdir()
            state=root/'state.json';state.write_bytes(b'old-state')
            outputs={}
            for name in ('a','b','c'):
                (root/name).write_bytes(('old-'+name).encode())
                source=root/('new-'+name);source.write_bytes(('new-'+name).encode());outputs[name]=source
            actual_replace=os.replace
            calls=0
            def failing_replace(source,target):
                nonlocal calls
                calls+=1
                if calls==2:raise PermissionError('simulated locked file')
                actual_replace(source,target)
            with patch('tools.installer.os.replace',side_effect=failing_replace):
                with self.assertRaises(PermissionError):commit_files(root,outputs,state,{'version':'new'})
            self.assertEqual(state.read_bytes(),b'old-state')
            for name in outputs:self.assertEqual((root/name).read_bytes(),('old-'+name).encode())
            self.assertEqual(list((root/'Scavland_Data').iterdir()),[])
            commit_files(root,outputs,state,{'version':'new'})
            for name in outputs:self.assertEqual((root/name).read_bytes(),('new-'+name).encode())
            self.assertEqual(r.read_json(state),{'version':'new'})

    def test_unknown_file_rejected_before_install(self):
        from tools.installer import inspect_game
        from tools.patch_core import GAME_FILES
        with tempfile.TemporaryDirectory(prefix='scavland-unit-') as tmp:
            game=Path(tmp);(game/'Scavland.exe').touch()
            originals={}
            for relative in GAME_FILES:
                path=game/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(relative.encode())
                originals[relative]={'sha256':r.file_digest(path),'size':path.stat().st_size}
            payload={'game':{'steam_build_id':'unit','original_files':originals}}
            sources,state,_=inspect_game(game,payload)
            self.assertIsNone(state['version'])
            next(iter(sources.values())).write_bytes(b'other mod')
            with self.assertRaisesRegex(ValueError,'Niezgodny plik'):inspect_game(game,payload)

    def test_catalog_changes_only_crc_record(self):
        import struct
        from tools.patch_core import EN,update_catalog
        prefix=b'unchanged'+EN.rsplit('/',1)[-1].encode()
        marker=struct.pack('<II',123,456)
        original=prefix+marker+b'end'
        result=update_catalog(original,123,456,789,999)
        self.assertEqual(result,prefix+struct.pack('<II',789,999)+b'end')
        with self.assertRaises(ValueError):update_catalog(original+marker,123,456,789,999)

if __name__=='__main__':unittest.main()
