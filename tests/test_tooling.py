"""Real offline CLI, packets, assembly, ingestion, vendor and migration tests."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True

from champollion.assemble import assemble_work, read_responses, validate_responses
from champollion.cli import main
from champollion.findings import ChampollionError
from champollion.format import parse_work
from champollion.packets import packet_documents, write_packets
from champollion.sources import add_source, local_path
from champollion.vendor import vendor, verify_vendor
from tests.fixtures.support import FIXTURES, REPO, TODAY, ProjectCase, tree_state, write_json


class CliCase(ProjectCase):
    def cli(self, *args, cwd=None):
        output, errors = io.StringIO(), io.StringIO()
        previous = Path.cwd()
        try:
            if cwd is not None:
                os.chdir(cwd)
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                status = main(list(map(str, args)))
        finally:
            os.chdir(previous)
        return status, output.getvalue(), errors.getvalue()

    def checked(self, *args, **kwargs):
        status, output, errors = self.cli(*args, **kwargs)
        self.assertEqual(status, 0, errors + output)
        self.assertEqual(errors, '')
        return json.loads(output)


class CliTests(CliCase):
    def test_check_lint_report_identical_json_and_no_writes(self):
        before = tree_state(self.root)
        reports = [self.checked(command, '--root', self.root, '--json') for command in ('check', 'lint', 'report')]
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(reports[0], reports[2])
        self.assertEqual(reports[0]['counts']['errors'], 0)
        self.assertEqual(tree_state(self.root), before)
        status, output, errors = self.cli('check', '--root', self.root, '--quiet')
        self.assertEqual((status, output, errors), (0, '', ''))

    def test_cli_finding_exit_one_warning_exit_zero_and_strict_one(self):
        self.replace_units([('One', 'Source')], [('One', 'Target')], [('One', 'Text .. continues.')])
        normal = self.cli('check', '--root', self.root, '--json')
        strict = self.cli('check', '--root', self.root, '--strict', '--json')
        self.assertEqual(normal[0], 0, normal[2])
        self.assertEqual(strict[0], 1, strict[2])
        self.assertEqual(json.loads(normal[1]), json.loads(strict[1]))
        self.assertEqual(json.loads(normal[1])['findings'][0]['severity'], 'warn')
        self.replace_units([('One', '1. Source')], [('One', '1. Target')], [('One', '2. Other target')])
        status, output, errors = self.cli('lint', '--root', self.root)
        self.assertEqual(status, 1, errors)
        self.assertIn('SEG-NUMBERING', output)
        self.assertEqual(errors, '')

    def test_cli_named_exit_two_usage_configuration_io_and_schema(self):
        for args, cause in [((), 'usage'), (('unknown-command',), 'usage'),
                            (('source', 'add'), 'usage'),
                            (('check', '--root', self.root, 'missing.md'), 'IO'),
                            (('check', '--root', self.root, '--profile', 'missing.json'), 'PROFILE-IO'),
                            (('check', '--root', self.root, 'works/synthetic.md', 'works/synthetic.md'), 'usage')]:
            with self.subTest(args=args):
                status, output, errors = self.cli(*args)
                self.assertEqual(status, 2)
                self.assertIn(cause + ':', errors)
                self.assertNotIn('0 errors', output)
        write_json(self.root / 'champollion.json', {})
        status, _, errors = self.cli('check', '--root', self.root)
        self.assertEqual(status, 2)
        self.assertIn('configuration:', errors)
        write_json(self.root / 'champollion.json', {'profile_path': 'profile.json'})
        (self.root / 'sources/manifest.json').write_text('{"records": [], "records": []}')
        status, _, errors = self.cli('check', '--root', self.root)
        self.assertEqual(status, 2)
        self.assertIn('schema:', errors)
        self.assertIn('duplicate JSON key', errors)

    def test_cli_broken_front_matter_never_clean(self):
        self.change_text('title:', 'slug: duplicate\ntitle:')
        status, output, errors = self.cli('check', '--root', self.root)
        self.assertEqual(status, 2)
        self.assertIn('SEG-FRONT-MATTER', errors)
        self.assertIn('synthetic.md', errors)
        self.assertNotIn('0 errors', output)

    def test_cli_profile_validate_and_rules_catalogue(self):
        profile = self.checked('profile', 'validate', self.root / 'profile.json', '--json')
        self.assertEqual(profile['profile'], 'champollion-profile/1')
        rules = self.checked('rules', '--json')['rules']
        ids = {r['id'] for r in rules}
        expected = set(re.findall(r'\*\*([A-Z]+-\d+)\b', (REPO / 'SPEC.md').read_text()))
        self.assertEqual(ids, expected)
        self.assertTrue(all(r['title'] for r in rules))
        (self.root / 'bad-profile.json').write_text('{"profile": 1}')
        status, _, errors = self.cli('profile', 'validate', self.root / 'bad-profile.json')
        self.assertEqual(status, 2)
        self.assertIn('PROFILE-SCHEMA:', errors)

    def test_cli_init_and_refuse_existing_scaffold(self):
        destination = Path(self.temp.name) / 'initialized'
        result = self.checked('init', destination, '--json')
        self.assertEqual(result['root'], str(destination))
        self.assertTrue((destination / 'works').is_dir())
        self.assertEqual(json.loads((destination / 'sources/manifest.json').read_text()), {'records': []})
        self.assertIn('profile_path', json.loads((destination / 'champollion.json').read_text()))
        before = tree_state(destination)
        status, _, errors = self.cli('init', destination)
        self.assertEqual(status, 2)
        self.assertIn('scaffold already exists', errors)
        self.assertEqual(tree_state(destination), before)

    def test_cli_baseline_requires_owned_dated_records_not_legacy_mapping(self):
        write_json(self.root / 'legacy.json', {'synthetic': {'archaism': ['Unit 1']}})
        status, _, errors = self.cli('check', '--root', self.root, '--baseline', 'legacy.json')
        self.assertEqual(status, 2)
        self.assertIn('legacy baselines are not VER-12 records', errors)
        self.replace_units([('One', 'Source')], [('One', 'Target')], [('One', 'Thou returnest.')])
        write_json(self.root / 'dated.json', {'exceptions': [{'code': 'REG-ARCHAISM', 'work': 'synthetic', 'unit': 'One',
                   'owner': 'synthetic test owner', 'reason': 'Artificial test only', 'recorded': '2026-01-01', 'expires': '9999-12-31'}]})
        report = self.checked('check', '--root', self.root, '--baseline', 'dated.json', '--json')
        self.assertEqual(report['counts']['errors'], 0)
        self.assertEqual(report['counts']['warnings'], 1)
        self.assertTrue(report['exceptions'][0]['applied'])

    def test_module_entrypoint_and_latin_to_spanish_end_to_end(self):
        root = REPO / 'examples/latin-to-spanish'
        before = tree_state(root)
        environment = dict(os.environ, PYTHONPATH=str(REPO / 'src'), PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, '-B', '-m', 'champollion', 'check', '--root', str(root), '--json'],
                                cwd=REPO, env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report['counts']['errors'], 0)
        self.assertEqual(report['profile']['settings']['target']['tag'], 'es')
        self.assertEqual({r['id'] for r in report['works'][0]['registers'] if r['present']}, {'literaria', 'clara'})
        self.assertEqual(report['publication_gate']['status'], 'blocked')
        self.assertFalse(report['judgement']['certifies_sense'])
        self.assertEqual(tree_state(root), before)


class PacketAssemblyTests(CliCase):
    def responses(self):
        return [(u.title, u.text) for u in self.work().register_section(self.profile(), 'plain').units]

    def response_directory(self, responses=None):
        path = Path(self.temp.name) / 'responses'
        path.mkdir(exist_ok=True)
        for index, (title, body) in enumerate(responses if responses is not None else self.responses()):
            (path / f'{index:06d}.md').write_text(f'### {title}\n\n{body}\n', encoding='utf-8')
        return path

    def test_packet_determinism_source_contract_and_register_isolation(self):
        work, profile = self.work(), self.profile()
        first = packet_documents(work, profile, 'plain', '1-4', str(self.root))
        self.assertEqual(first, packet_documents(work, profile, 'plain', '1-4', str(self.root)))
        self.assertEqual([d['filename'] for d in first], ['000001-unit-1.md', '000002-unit-2.md', '000003-unit-3.md', '000004-unit-4.md'])
        for packet, source in zip(first, work.original().units):
            self.assertIn(source.text, packet['text'])
            for rule in ('WRK-1', 'WRK-2', 'WRK-3', 'WRK-4'):
                self.assertIn(rule, packet['text'])
            self.assertIn('Exact response shape', packet['text'])
            self.assertIn('Ordered markers:', packet['text'])
            self.assertIn('——', packet['text'])
            self.assertNotIn(work.register_section(profile, 'musean').units[0].text, packet['text'])
        out = Path(self.temp.name) / 'packets'
        write_packets(work, profile, 'plain', '1-4', str(self.root), str(out))
        before = {p.name: p.read_bytes() for p in out.glob('*.md')}
        write_packets(work, profile, 'plain', '1-4', str(self.root), str(out))
        self.assertEqual({p.name: p.read_bytes() for p in out.glob('*.md')}, before)

    def test_packet_bad_ranges_and_register_refused(self):
        for units in ('0-1', '1', '2-1', '1-5', '-1-2', '1-1 trailing'):
            with self.subTest(units=units), self.assertRaises(ChampollionError):
                packet_documents(self.work(), self.profile(), 'plain', units, str(self.root))
        with self.assertRaises(ChampollionError):
            packet_documents(self.work(), self.profile(), 'undeclared', '1-1', str(self.root))

    def test_cli_packets_json_and_explicit_output(self):
        result = self.checked('packets', '--root', self.root, '--register', 'plain', '--units', '1-2', '--json')
        self.assertEqual(len(result['packets']), 2)
        out = Path(self.temp.name) / 'cli-packets'
        result = self.checked('packets', '--root', self.root, '--register', 'plain', '--units', '1-2', '--out', out, '--json')
        self.assertEqual(len(result['files']), 2)
        self.assertTrue(all(Path(f['path']).is_file() for f in result['files']))

    def test_assembly_missing_duplicate_unknown_out_of_order_empty_and_marker_refusal(self):
        good = self.responses()
        cases = [(good[:-1], 'WRK-5', 'missing'), (good + [good[0]], 'WRK-5', 'duplicate'),
                 ([('Alien', good[0][1])] + good[1:], 'WRK-5', 'unknown'),
                 (list(reversed(good)), 'WRK-5', 'order'),
                 ([(good[0][0], '')] + good[1:], 'WRK-5', 'empty'),
                 ([(good[0][0], good[0][1].replace('1.', '2.', 1))] + good[1:], 'SEG-NUMBERING', 'marker'),
                 ([(good[0][0], good[0][1].replace('——', ''))] + good[1:], 'SEG-COVERAGE', 'blank')]
        before = tree_state(self.root)
        validate_responses(self.work(), good)
        for responses, cause, message in cases:
            with self.subTest(message=message), self.assertRaises(ChampollionError) as caught:
                validate_responses(self.work(), responses)
            self.assertEqual(caught.exception.cause, cause)
            self.assertIn(message, str(caught.exception))
        self.assertEqual(tree_state(self.root), before)

    def test_response_reader_refuses_malformed_duplicate_heading_and_comment_only(self):
        directory = self.response_directory([])
        path = directory / '000001.md'
        for text in ('no heading', '## Section\nText', '### One\n', '### One\n<!-- nothing -->',
                     '### One\nText\n### Two\nText', '### One\nText\n## Section'):
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaises(ChampollionError): read_responses(str(directory))

    def test_assembly_writes_copy_not_original_and_refuses_second_overwrite(self):
        directory = self.response_directory()
        original = self.work_path.read_bytes()
        result = assemble_work(self.work(), self.profile(), 'plain', str(directory))
        output = Path(result['output'])
        self.assertNotEqual(output, self.work_path)
        self.assertEqual(self.work_path.read_bytes(), original)
        assembled = parse_work(output)
        self.assertEqual([u.text for u in assembled.register_section(self.profile(), 'plain').units],
                         [body for _, body in self.responses()])
        before = output.read_bytes()
        with self.assertRaises(ChampollionError): assemble_work(self.work(), self.profile(), 'plain', str(directory))
        self.assertEqual(output.read_bytes(), before)

    def test_cli_assemble_and_named_contract_error(self):
        directory = self.response_directory()
        original = self.work_path.read_bytes()
        result = self.checked('assemble', '--register', 'plain', '--from', directory, '--work', self.work_path, '--json', cwd=self.root)
        self.assertEqual(result['units'], 4)
        self.assertEqual(self.work_path.read_bytes(), original)
        Path(result['output']).unlink()
        (directory / '000003.md').unlink()
        status, output, errors = self.cli('assemble', '--register', 'plain', '--from', directory, '--work', self.work_path, cwd=self.root)
        self.assertEqual(status, 2)
        self.assertIn('WRK-5:', errors)
        self.assertFalse(Path(result['output']).exists())


class SourceVendorTests(CliCase):
    def ingest(self, **changes):
        defaults = dict(id='new-source', file=str(self.root / 'input.bin'), provider='synthetic provider',
                        edition='original test bytes', revision='catalogue:synthetic-v1', rights='CC0-1.0')
        defaults.update(changes)
        return add_source(str(self.root), self.profile(), **defaults)

    def test_source_add_stores_exact_bytes_hash_and_requires_replace(self):
        data = b'Original synthetic\r\nbytes\x00\xff\n'
        (self.root / 'input.bin').write_bytes(data)
        result = self.ingest()
        self.assertEqual(result['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual((self.root / result['path']).read_bytes(), data)
        self.assertEqual(self.ingest()['sha256'], result['sha256'])
        (self.root / 'input.bin').write_bytes(b'changed')
        before = tree_state(self.root)
        with self.assertRaises(ChampollionError) as caught: self.ingest()
        self.assertEqual(caught.exception.cause, 'source-conflict')
        self.assertEqual(tree_state(self.root), before)
        replacement = self.ingest(replace=True)
        self.assertEqual(replacement['sha256'], hashlib.sha256(b'changed').hexdigest())
        self.assertNotEqual(replacement['path'], result['path'])
        self.assertEqual((self.root / result['path']).read_bytes(), data)
        records = json.loads((self.root / 'sources/manifest.json').read_text())['records']
        self.assertEqual(sum(r['id'] == 'new-source' for r in records), 1)

    def test_source_rights_url_missing_file_and_traversal_refused_without_writes(self):
        (self.root / 'input.bin').write_bytes(b'synthetic')
        for changes, cause in [({'rights': 'unknown'}, 'SRC-RIGHTS'), ({'file': 'missing.bin'}, 'IO'),
                               ({'id': '../escape'}, 'configuration'), ({'id': '/absolute'}, 'configuration'),
                               ({'provider': ''}, 'schema')]:
            before = tree_state(self.root)
            with self.subTest(changes=changes), self.assertRaises(ChampollionError) as caught: self.ingest(**changes)
            self.assertEqual(caught.exception.cause, cause)
            self.assertEqual(tree_state(self.root), before)
        before = tree_state(self.root)
        with self.assertRaises(ChampollionError) as caught:
            self.ingest(file=None, url='https://example.invalid/source?a=1&b=2')
        self.assertEqual(caught.exception.cause, 'source-acquisition')
        self.assertIn('curl --fail --location', str(caught.exception))
        self.assertIn('champollion source add', str(caught.exception))
        self.assertEqual(tree_state(self.root), before)
        for path in ('../escape', '/absolute', 'https://example.invalid/raw', ''):
            with self.subTest(path=path), self.assertRaises(ChampollionError): local_path(self.root, path)
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        (self.root / 'escape').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ChampollionError): local_path(self.root, 'escape/raw.txt')

    def test_cli_source_add_and_named_acquisition_refusal(self):
        data = b'Small original synthetic snapshot.\r\n'
        (self.root / 'input.bin').write_bytes(data)
        flags = ('--id', 'new-source', '--provider', 'synthetic', '--edition', 'test',
                 '--revision', 'catalogue:synthetic-v1', '--rights', 'CC0-1.0', '--root', self.root)
        result = self.checked('source', 'add', *flags, '--file', self.root / 'input.bin', '--json')
        self.assertEqual(result['sha256'], hashlib.sha256(data).hexdigest())
        status, _, errors = self.cli('source', 'add', *flags, '--url', 'https://example.invalid/source')
        self.assertEqual(status, 2)
        self.assertIn('source-acquisition:', errors)

    def test_vendor_exact_manifest_missing_extra_modified_and_path_execution(self):
        destination = Path(self.temp.name) / 'vendor'
        result = vendor(str(destination), tag='synthetic-test-tag', today=TODAY)
        package = Path(result['directory'])
        self.assertTrue(verify_vendor(str(destination))['valid'])
        for name, digest in result['manifest']['files'].items():
            self.assertEqual(hashlib.sha256((package / name).read_bytes()).hexdigest(), digest)
        run = subprocess.run([sys.executable, '-B', str(package / '__main__.py'), 'rules', '--json'],
                             cwd=destination, env=dict(os.environ, PYTHONPATH='', PYTHONDONTWRITEBYTECODE='1'),
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('rules', json.loads(run.stdout))
        self.assertTrue(verify_vendor(str(destination))['valid'], 'path execution must not mutate vendor')
        (package / 'findings.py').write_text('# changed synthetic test\n')
        (package / 'profile.py').unlink()
        (package / 'extra.txt').write_text('untracked')
        report = verify_vendor(str(destination))
        self.assertFalse(report['valid'])
        self.assertIn('findings.py', report['mismatches'])
        self.assertIn('profile.py', report['missing'])
        self.assertIn('extra.txt', report['extra'])
        status, output, errors = self.cli('verify-vendor', destination, '--json')
        self.assertEqual(status, 1, errors)
        self.assertFalse(json.loads(output)['valid'])

    def test_vendor_manifest_traversal_absolute_nonhash_and_symlink_refused(self):
        destination = Path(self.temp.name) / 'vendor'
        result = vendor(str(destination), today=TODAY)
        package = Path(result['directory'])
        manifest_path = package / 'VENDOR.json'
        original = result['manifest']
        for name, digest in [('../escape', '0'*64), ('/absolute', '0'*64), ('./findings.py', '0'*64),
                             ('findings.py', 'not-a-sha256'), ('VENDOR.json', '0'*64)]:
            malformed = dict(original, files={name: digest})
            write_json(manifest_path, malformed)
            with self.subTest(name=name), self.assertRaises(ChampollionError) as caught: verify_vendor(str(destination))
            self.assertEqual(caught.exception.cause, 'schema')
        write_json(manifest_path, original)
        (package / 'link.py').symlink_to(package / 'findings.py')
        report = verify_vendor(str(destination))
        self.assertFalse(report['valid'])
        self.assertIn('link.py', report['symlinks'])

    def test_cli_vendor_and_refuse_existing_destination(self):
        destination = Path(self.temp.name) / 'cli-vendor'
        self.checked('vendor', '--into', destination, '--tag', 'synthetic-test', '--json')
        self.assertTrue(self.checked('verify-vendor', destination, '--json')['valid'])
        before = tree_state(destination)
        status, _, errors = self.cli('vendor', '--into', destination)
        self.assertEqual(status, 2)
        self.assertIn('destination already exists', errors)
        self.assertEqual(tree_state(destination), before)


class LegacyCompatibilityTests(CliCase):
    def test_mouseia_legacy_pass_fail_baseline_counts_not_conformance(self):
        from champollion.compat import mouseia
        corpus = self.root / 'corpus'; corpus.mkdir()
        scripts = self.root / 'scripts'; scripts.mkdir()
        write_json(scripts / 'names.json', {})
        work = corpus / 'synthetic.md'
        work.write_bytes(self.work_path.read_bytes())
        errors, warnings = mouseia.lint(str(work), {}, {})
        self.assertEqual((errors, warnings), ([], []))
        with work.open('a') as handle: handle.write('\nThou art here.\n')
        errors, warnings = mouseia.lint(str(work), {}, {})
        self.assertEqual((len(errors), len(warnings)), (1, 0))
        self.assertIn('archaism:', errors[0])
        baseline = {'synthetic': {'archaism': ['Unit 4']}}
        errors, warnings = mouseia.lint(str(work), baseline, {})
        self.assertEqual((len(errors), len(warnings)), (0, 1))
        write_json(scripts / 'lint-baseline.json', baseline)
        output, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(stderr):
            status = mouseia.main(['--verbose'], root=str(self.root))
        self.assertEqual(status, 0)
        self.assertIn('1 works, 0 errors, 1 warnings/baselined', output.getvalue())
        self.assertNotIn('eligible', output.getvalue().lower())
        self.assertNotIn('conform', output.getvalue().lower())
        self.assertEqual(self.report()['publication_gate']['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
