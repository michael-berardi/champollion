"""Strict file parsing and profile schema tests against the real runtime."""
import copy
import hashlib
import json
import sys
import unittest

sys.dont_write_bytecode = True

from champollion.findings import ChampollionError, Finding, format_finding, findings_json
from champollion.format import WorkFormatError, parse_front_matter, parse_work
from champollion.profile import load_profile, profile_json, validate_profile
from tests.fixtures.support import FIXTURES, ProjectCase, write_json


class FrontMatterTests(ProjectCase):
    def test_scalar_and_json_quoted_values_preserved_with_crlf(self):
        text = '---\r\nslug: synthetic\r\ntruth: true\r\nnumber: 003\r\ndate: 2026-01-01\r\nnullish: null\r\ncolon: a: b # text\r\nquoted: "[a] \\t \\"word\\""\r\n---\r\nbody'
        front, start = parse_front_matter(text, 'synthetic.md')
        self.assertEqual(start, 10)
        self.assertEqual(front, {'slug': 'synthetic', 'truth': 'true', 'number': '003',
                                'date': '2026-01-01', 'nullish': 'null', 'colon': 'a: b # text',
                                'quoted': '[a] \t "word"'})

    def test_malformed_front_matter_named_file_and_line(self):
        fields = [' slug: x', 'Slug: x', 'slug x', '', '# comment', 'a: [x]', 'a: {x}',
                  'a: - x', 'a: |', 'a: >', 'a: "x" trailing', 'a: "bad\\q"',
                  'a: "line\\nnext"', 'a: "line\\rnext"', 'a: "unterminated',
                  'slug: x\nslug: y', 'a: x\n  child: y']
        for field in fields:
            with self.subTest(field=field):
                with self.assertRaises(WorkFormatError) as caught:
                    parse_front_matter('---\n' + field + '\n---\n', 'bad.md')
                self.assertEqual(caught.exception.code, 'SEG-FRONT-MATTER')
                self.assertIn('bad.md', str(caught.exception))
                self.assertIn('line ', str(caught.exception))
        for text in ('slug: x\n---\n', '\ufeff---\nslug: x\n---\n', '---\nslug: x', ' ---\nslug: x\n---'):
            with self.subTest(text=text), self.assertRaises(WorkFormatError):
                parse_front_matter(text, 'bad.md')

    def test_empty_scalar_is_preserved_not_defaulted(self):
        front, _ = parse_front_matter('---\ntitle:\n---\n', 'empty.md')
        self.assertEqual(front['title'], '')

    def test_extra_scalar_and_unknown_sections_preserved_comments_removed(self):
        self.change_text('title:', 'extra: "[uninterpreted]"\ntitle:')
        with self.work_path.open('a') as handle:
            handle.write('\n## Unknown section\n\nUnheaded preserved text.\n')
        self.change_text('1. A small bird', '<!-- excluded -->\n1. A small bird')
        before = self.work_path.read_bytes()
        work = self.work()
        self.assertEqual(work.front['extra'], '[uninterpreted]')
        self.assertIsNotNone(work.section(' UNKNOWN SECTION '))
        self.assertNotIn('excluded', work.original().units[0].text)
        self.assertEqual(before, self.work_path.read_bytes())

    def test_duplicate_sections_units_and_empty_headings_refused(self):
        variants = ['## Original\n### One\nText\n## original\n',
                    '## Unknown\n## UNKNOWN\n', '## Original\n### One\nText\n### One\nText\n',
                    '## Original\n### \nText\n', '## \n', '### Stray\nText\n',
                    '## Original\nUnheaded source text\n### One\nText\n']
        prefix = self.work_path.read_text().split('\n## Original', 1)[0]
        for body in variants:
            with self.subTest(body=body):
                self.work_path.write_text(prefix + '\n' + body)
                with self.assertRaises(WorkFormatError) as caught:
                    self.work()
                self.assertEqual(caught.exception.code, 'SEG-PARITY')

    def test_alias_duplicates_refused_and_label_is_not_alias(self):
        with self.work_path.open('a') as handle:
            handle.write('\n## Curated translation\n### Unit 1\nText\n')
        with self.assertRaises(WorkFormatError) as caught:
            self.work().register_section(self.profile(), 'musean')
        self.assertEqual(caught.exception.code, 'SEG-PARITY')
        self.change_text('## Mouseia translation', '## Musean')
        self.change_text('## Curated translation', '## Other')
        self.assertIsNone(self.work().register_section(self.profile(), 'musean'))

    def test_unit_titles_trim_outer_space_but_keep_case(self):
        self.change_text('### Unit 1', '###   Unit 1   ')
        self.assertEqual(self.work().original().units[0].title, 'Unit 1')
        self.assertNotEqual(self.work().original().units[0].title, 'unit 1')

    def test_no_implicit_whole_work_unit(self):
        prefix = self.work_path.read_text().split('\n## Original', 1)[0]
        self.work_path.write_text(prefix + '\n## Original\n')
        self.assertEqual(self.work().original().units, [])

    def test_invalid_utf8_is_named_io_error(self):
        self.work_path.write_bytes(b'\xff')
        with self.assertRaises(WorkFormatError) as caught:
            self.work()
        self.assertIn(str(self.work_path), str(caught.exception))
        self.assertEqual(caught.exception.cause, 'WORK-IO')


class ProfileTests(ProjectCase):
    def test_valid_roundtrip_optional_language_omission_and_byte_fingerprint(self):
        profile = load_profile(self.root / 'profile.json')
        self.assertEqual(profile.fingerprint, 'sha256:' + hashlib.sha256((self.root / 'profile.json').read_bytes()).hexdigest())
        self.assertEqual(profile_json(validate_profile(profile_json(profile), 'roundtrip.json')), profile_json(profile))
        obj = self.settings()
        for key in ('source', 'target', 'target_locale'):
            obj.pop(key)
        unspecified = validate_profile(obj, 'unspecified.json')
        self.assertIsNone(unspecified.source)
        self.assertIsNone(unspecified.target)
        self.assertIsNone(unspecified.target_locale)

    def test_duplicate_json_keys_at_each_depth_and_invalid_json_rejected(self):
        source = (self.root / 'profile.json').read_text()
        cases = [source.replace('"name":', '"name": "duplicate", "name":', 1),
                 source.replace('"structure":', '"structure": false, "structure":', 1),
                 source.replace('"id":', '"id": "duplicate", "id":', 1),
                 source.replace('"allowed":', '"allowed": [], "allowed":', 1),
                 source + '{}', source + ' trailing', source.replace('0.35', 'NaN'),
                 source.replace('0.35', 'Infinity'), source.replace('0.35', '-Infinity'),
                 source.replace('"name":', '// comment\n"name":', 1), source[:-2] + ',\n}']
        for text in cases:
            with self.subTest(text=text[:70]):
                (self.root / 'bad.json').write_text(text)
                with self.assertRaises(ChampollionError) as caught:
                    load_profile(self.root / 'bad.json')
                self.assertIn('bad.json', str(caught.exception))

    def test_profile_schema_rejection_matrix(self):
        base = self.settings()
        exception = {'code': 'REG-ARCHAISM', 'work': 'synthetic', 'unit': 'Unit 1',
                     'owner': 'test owner', 'reason': 'Synthetic test only',
                     'recorded': '2026-01-01', 'expires': '2026-01-03'}
        mutations = []
        def add(path, value):
            mutations.append((path, value))
        for field in ('profile', 'name', 'description', 'registers', 'checks', 'rights', 'exceptions'):
            obj = copy.deepcopy(base); obj.pop(field)
            mutations.append((('DELETE', field), obj))
        for path, values in {
            ('profile',): ['champollion-profile/2', True], ('name',): ['', 1], ('description',): ['', False],
            ('source',): ['la', {'tag': 'la'}, {'tag': 'bad_tag', 'name': 'Latin'}, {'tag': 'la', 'name': 'Latin', 'extra': 1}],
            ('target',): [{'tag': 'en', 'name': ''}], ('target_locale',): ['', 'bad_tag', 'es-MX', 1],
            ('registers',): [[], {}, 'musean'],
            ('registers', 0, 'id'): ['Original', 'original', '1bad', 'Bad', 'plain', ''],
            ('registers', 0, 'label'): ['', 1], ('registers', 0, 'required'): ['true', 1],
            ('registers', 0, 'alignment'): ['none', 'by-position', 'unsupported'],
            ('registers', 0, 'sections'): [[], 'alias', [''], ['original'], ['plain translation'], ['A', ' a ']],
            ('checks',): [[], {}], ('checks', 'archaisms'): ['en', True],
            ('checks', 'ellipsis'): ['warning', False], ('checks', 'spelling_profile'): ['fr', True],
            ('checks', 'name_table'): ['', 'https://example.invalid/names.json', [], False],
            ('checks', 'speech_marks'): ['plain', ['missing'], ['plain', 'plain'], [False]],
            ('rights',): [[], {}, {'allowed': ['CC0-1.0'], 'extra': 1}],
            ('rights', 'allowed'): [[], '', [''], [False], ['CC0-1.0', 'CC0-1.0']],
            ('exceptions',): [{}, [False]],
        }.items():
            for value in values: add(path, value)
        for field in ('structure', 'coverage', 'numbering', 'plain_archaisms', 'debris'):
            for value in (0, 'true', None): add(('checks', field), value)
        for field in ('copy_ratio', 'short_unit_ratio'):
            for value in (True, '0.5', -0.1, 1.1, float('nan'), float('inf')): add(('checks', field), value)
        add(('checks', 'short_unit_ratio'), 0)
        for field in ('min_source_chars', 'min_units_for_ratio', 'min_sentences', 'min_sentence_chars'):
            for value in (True, '3', 0, 3.0): add(('checks', field), value)
        add(('checks', 'min_units_for_ratio'), 2)
        add(('checks', 'archaisms'), 'off')  # plain_archaisms still true
        for path in ((), ('registers', 0), ('checks',), ('rights',), ('source',)):
            obj = copy.deepcopy(base)
            if path == ('source',): obj['source'] = {'tag': 'en', 'name': 'English'}
            target = obj
            for key in path: target = target[key]
            target['unexpected'] = True
            mutations.append((('OBJECT', str(path)), obj))
        for field in base['registers'][0]:
            obj = copy.deepcopy(base); del obj['registers'][0][field]
            mutations.append((('OBJECT', 'missing register ' + field), obj))
        for field in base['checks']:
            obj = copy.deepcopy(base); del obj['checks'][field]
            mutations.append((('OBJECT', 'missing check ' + field), obj))
        for field in exception:
            obj = copy.deepcopy(base); obj['exceptions'] = [dict(exception)]; del obj['exceptions'][0][field]
            mutations.append((('OBJECT', 'missing exception ' + field), obj))
        for field, values in {'code': ['archaism', 'REG_archaism', ''], 'work': ['', 1], 'unit': ['', None],
                              'owner': ['', False], 'reason': ['', []], 'recorded': ['2026-02-30', '20260101', '2026-1-1'],
                              'expires': ['2026-01-01', '2025-12-31', '2026-02-30']}.items():
            for value in values:
                obj = copy.deepcopy(base); obj['exceptions'] = [dict(exception, **{field: value})]
                mutations.append((('OBJECT', 'exception ' + field), obj))
        obj = copy.deepcopy(base); obj['exceptions'] = [exception, dict(exception)]
        mutations.append((('OBJECT', 'duplicate exception'), obj))
        obj = copy.deepcopy(base); obj['registers'][1]['id'] = 'direct'; obj['checks']['speech_marks'] = []
        mutations.append((('OBJECT', 'Plain policy without plain'), obj))
        for path, value in mutations:
            obj = copy.deepcopy(base)
            if path[0] in ('DELETE', 'OBJECT'): obj = value
            else:
                parent = obj
                for key in path[:-1]: parent = parent[key]
                parent[path[-1]] = value
            with self.subTest(path=path, value=value), self.assertRaises(ChampollionError) as caught:
                validate_profile(obj, 'invalid-profile.json')
            self.assertIn('invalid-profile.json', str(caught.exception))

    def test_threshold_edges_and_gregorian_leap_day_accepted(self):
        obj = self.settings()
        obj['checks'].update(copy_ratio=0, short_unit_ratio=1)
        obj['exceptions'] = [{'code': 'REG-ARCHAISM', 'work': 'synthetic', 'unit': 'Unit 1',
                              'owner': 'test owner', 'reason': 'Test input', 'recorded': '2024-02-29', 'expires': '2024-03-01'}]
        validate_profile(obj, 'valid.json')
        obj['checks'].update(copy_ratio=1, short_unit_ratio=None)
        validate_profile(obj, 'valid.json')


class FindingTests(unittest.TestCase):
    def test_stable_format_json_and_exception_visibility(self):
        f = Finding('SEG-NUMBERING', 'SEG-5', 'error', 'marker differs', work='bird', unit='One', evidence={'expected': ['1.']})
        self.assertEqual(format_finding(f), 'ERROR bird [One] SEG-NUMBERING: marker differs')
        self.assertIn('[exception]', format_finding(f, {'owner': 'test'}))
        self.assertEqual(findings_json([f])[0]['rule'], 'SEG-5')
        work_level = Finding('SRC-8', 'SRC-8', 'error', 'missing snapshot', work='bird')
        self.assertEqual(format_finding(work_level), 'ERROR bird SRC-8: missing snapshot')


if __name__ == '__main__':
    unittest.main()
