"""Parent regression tests for portability, freshness and generalized policies."""
import hashlib
import json
from pathlib import Path
import unittest

from champollion.checks import hygiene
from champollion.assemble import assemble_work, validate_responses
from champollion.findings import ChampollionError
from champollion.packets import packet_documents
from champollion.report import build_report
from champollion.cli import _init, _profile
from champollion.profile import validate_profile, load_profile
from champollion.sources import add_source
from tests.fixtures.support import REPO, TODAY, ProjectCase


class ReviewFreshnessTests(ProjectCase):
    def current_review(self):
        return {
            'reviewer': 'Synthetic test reviewer; not a real translation review',
            'date': TODAY, 'protocol_version': '1.0.0', 'work': 'synthetic',
            'units': [u.title for u in self.work().original().units],
            'registers': ['musean', 'plain'], 'findings': [], 'resolutions': [],
            'work_sha256': hashlib.sha256(self.work_path.read_bytes()).hexdigest(),
            'source_sha256': self.sources()['synthetic']['sha256'],
            'profile_fingerprint': self.profile().fingerprint,
        }

    def test_current_review_is_bound_to_exact_work_source_and_profile(self):
        self.record(reviews=[self.current_review()])
        self.assertEqual(self.report()['publication_gate']['status'], 'eligible')
        self.work_path.write_text(self.work_path.read_text() + '\n', encoding='utf-8')
        result = self.report()
        self.assertEqual(result['counts']['errors'], 0)
        self.assertEqual(result['publication_gate']['status'], 'blocked')

    def test_source_and_profile_changes_invalidate_old_review(self):
        self.record(reviews=[self.current_review()])
        self.assertEqual(self.report()['publication_gate']['status'], 'eligible')
        self.assertEqual(self.report(self.profile(min_sentences=5))['publication_gate']['status'], 'blocked')
        raw = self.root / 'sources/raw/synthetic.txt'
        raw.write_bytes(raw.read_bytes() + b'\n')
        self.record(sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
        self.assertEqual(self.report()['counts']['errors'], 0)
        self.assertEqual(self.report()['publication_gate']['status'], 'blocked')

    def test_unbound_declarations_do_not_certify_current_text(self):
        review = self.current_review()
        for key in ('work_sha256', 'source_sha256', 'profile_fingerprint'):
            review.pop(key)
        self.record(reviews=[review])
        self.assertEqual(self.report()['publication_gate']['status'], 'blocked')


class PortablePolicyTests(ProjectCase):
    def test_generic_and_nonenglish_quote_conventions_are_not_english_debris(self):
        settings = self.settings()
        settings.update(source=None, target=None, target_locale=None)
        settings['checks'].update(archaisms='off', plain_archaisms=False, spelling_profile=None, name_table=None)
        self.replace_units([('One', '1. Original.')], [('One', '1. «Texte» avec {notation} et x^2.')], [('One', '1. «Texto» con {notación} y x^2.')])
        for target in (None, {'tag': 'es', 'name': 'Spanish'}):
            settings['target'] = target
            profile = validate_profile(settings, 'synthetic.json')
            self.assertEqual(hygiene.run(self.context(profile)), [])
            states = hygiene.statuses(self.context(profile), [])
            self.assertTrue(any(s['check'] == 'hygiene.doubled_word' and s['status'] == 'inapplicable' for s in states))

    def test_init_copies_a_portable_profile_and_survives_project_move(self):
        directory = self.root / 'new-project'
        _init(str(directory))
        config = json.loads((directory / 'champollion.json').read_text())
        self.assertEqual(config['profile_path'], 'profiles/generic.json')
        moved = self.root / 'moved-project'
        directory.rename(moved)
        self.assertEqual(_profile(moved).name, 'generic')

    def test_manifest_line_contract_is_shared_by_packets_and_assembly(self):
        self.replace_units([('One', '1. First source line.\nA second source line.')],
                           [('One', '1. First rendering.\nA second rendering.')],
                           [('One', '1. First plain line.\nA second plain line.')])
        self.record(numbering={'notation': 'leading-number', 'line_for_line': True})
        packet = packet_documents(self.work(), self.profile(), 'plain', '1-1', str(self.root))[0]
        self.assertIn('Return exactly 2 nonempty target lines', packet['text'])
        with self.assertRaises(ChampollionError) as caught:
            validate_responses(self.work(), [('One', '1. Merged target line.')], str(self.root))
        self.assertEqual(caught.exception.cause, 'SEG-NUMBERING')
        responses = self.root / 'responses'
        responses.mkdir()
        (responses / '000001.md').write_text('### One\n\n1. First plain line.\nA second plain line.\n', encoding='utf-8')
        result = assemble_work(self.work(), self.profile(), 'plain', str(responses), str(self.root))
        self.assertEqual(Path(result['output']).name, self.work_path.name)
        report = build_report([result['output']], self.profile(), str(self.root), TODAY)
        self.assertEqual(report['counts']['errors'], 0)

    def test_first_work_guide_uses_project_configuration_and_local_profile(self):
        project = self.root / 'walkthrough'
        _init(str(project))
        path = project / 'profiles/generic.json'
        settings = json.loads(path.read_text())
        settings['registers'][0].update(id='musean', label='Musean', sections=['Musean'])
        settings['registers'][1].update(label='Plain English', sections=['Plain English'])
        settings['target'] = {'tag': 'en', 'name': 'English'}
        path.write_text(json.dumps(settings), encoding='utf-8')
        profile = load_profile(path)
        self.assertEqual(_profile(project).fingerprint, profile.fingerprint)
        original = project / 'original.txt'
        original.write_text('Sol super colles oritur.\nAvis in arbore cantat.\n', encoding='utf-8')
        record = add_source(str(project), profile, id='sunrise', file=str(original), provider='local',
                            edition='Sunrise teaching edition', revision='sunrise-v1', rights='public-domain')
        manifest_path = project / 'sources/manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['records'][0].update(rights={'work': 'public-domain', 'transcription': 'public-domain'},
                                      cleaning={'rule': 'No source changes'}, numbering={'line_for_line': True})
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        fields = {'slug':'sunrise','title':'Sunrise','author':'Champollion documentation','tradition':'teaching',
                  'language':'la','genre':'two-line teaching composition','period':'contemporary',
                  'source_url':'urn:champollion:teaching:sunrise','raw_snapshot':record['path'],
                  'completeness':'complete','source_scope':'whole-work','as_of':TODAY,'certainty':'synthetic test',
                  'source':'sources/manifest.json#sunrise','status':'Draft','unknowns':'Synthetic demonstration; no judgement review',
                  'musean_translator':'Synthetic test contributor','musean_note':'Demonstration only',
                  'plain_translator':'Synthetic test contributor','plain_note':'Demonstration only'}
        body = ('\n## Original\n\n### Morning\n\nSol super colles oritur.\nAvis in arbore cantat.\n'
                '\n## Musean\n\n### Morning\n\nThe sun rises above the hills.\nA bird sings in the tree.\n'
                '\n## Plain English\n\n### Morning\n\nAbove the hills, the sun is coming up.\nThere is a bird singing in the tree.\n')
        work = project / 'works/sunrise.md'
        work.write_text('---\n' + '\n'.join(f'{key}: {json.dumps(value)}' for key,value in fields.items()) + '\n---\n' + body, encoding='utf-8')
        report = build_report([work], profile, str(project), TODAY)
        self.assertEqual(report['counts']['errors'], 0)
        self.assertEqual(report['checker_version'], '1.2.2')
        self.assertEqual(report['protocol_version'], '1.0.0')
        self.assertEqual(report['publication_gate']['status'], 'blocked')

    def test_installed_profile_resources_match_canonical_profiles(self):
        for profile in (REPO / 'profiles').glob('*.json'):
            self.assertEqual(profile.read_bytes(), (REPO / 'src/champollion/profiles' / profile.name).read_bytes())


if __name__ == '__main__':
    unittest.main()
