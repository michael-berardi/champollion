"""Adversarial mechanical gates, measured boundaries, and exception debt."""
import copy
import json
import sys
import unittest

sys.dont_write_bytecode = True

from champollion.checks import CHECKS, run_checks
from champollion.checks import coverage, hygiene, language, numbering, provenance, register, rights, speech, structure
from champollion.findings import ChampollionError
from champollion.format import WorkFormatError, parse_work
from champollion.profile import load_profile, validate_profile
from champollion.report import build_report, render_text
from tests.fixtures.support import FIXTURES, TODAY, ProjectCase, codes, tree_state, write_json


class FixtureTests(unittest.TestCase):
    def test_required_synthetic_fixture_findings(self):
        for root in sorted(p for p in FIXTURES.iterdir() if p.is_dir() and not p.name.startswith('.')):
            expected_path = root / 'expected.json'
            if not expected_path.exists():
                continue
            expected = json.loads(expected_path.read_text())['code']
            with self.subTest(fixture=root.name):
                profile = load_profile(root / 'profile.json')
                if expected == 'SEG-FRONT-MATTER':
                    with self.assertRaises(WorkFormatError) as caught:
                        build_report([root / 'works/synthetic.md'], profile, str(root), TODAY)
                    self.assertEqual(caught.exception.code, expected)
                    continue
                report = build_report([root / 'works/synthetic.md'], profile, str(root), TODAY)
                found = [row['code'] for row in report['findings']]
                if expected:
                    self.assertIn(expected, found)
                    self.assertGreater(report['counts']['errors'], 0)
                else:
                    self.assertEqual(found, [])
                    self.assertEqual(report['counts']['errors'], 0)
                    self.assertEqual(report['publication_gate']['status'], 'blocked')
                    self.assertFalse(report['judgement']['certifies_sense'])

    def test_clean_fixture_runs_every_family_without_error(self):
        root = FIXTURES / 'clean'
        report = build_report([root / 'works/synthetic.md'], load_profile(root / 'profile.json'), str(root), TODAY)
        statuses = {g['check']: g['status'] for g in report['works'][0]['gates']}
        for check in CHECKS:
            self.assertIn(statuses[check.name], ('ran', 'inapplicable'))
        self.assertEqual(statuses['register'], 'ran')  # exactly min_sentences eligible sentences qualifies; not independence proof
        self.assertEqual(statuses['coverage.short_unit_ratio'], 'ran')
        self.assertEqual(report['review_records'], [])


class StructureCoverageTests(ProjectCase):
    def test_structure_pass_missing_original_register_and_empty_unit_fail(self):
        self.assertEqual(structure.run(self.context()), [])
        self.change_text('## Original', '## Source omitted')
        self.assertIn('SEG-PARITY', codes(structure.run(self.context())))
        self.change_text('## Mouseia translation', '## Undeclared')
        self.assertIn('REG-1', codes(structure.run(self.context())))
        self.replace_units([('One', '1. Source')], [('One', '')], [('One', '1. Target')])
        self.assertIn('REG-1', codes(structure.run(self.context())))
        self.assertIn('SEG-COVERAGE', codes(coverage.run(self.context())))

    def test_title_case_order_and_slug_mismatch_fail(self):
        self.change_text('## Plain English translation\n\n### Unit 1', '## Plain English translation\n\n### unit 1')
        found = structure.run(self.context())
        parity = next(f for f in found if f.code == 'SEG-PARITY')
        self.assertEqual(parity.evidence['position'], 1)
        self.change_text('slug: "synthetic"', 'slug: "another"')
        self.assertIn('SEG-FRONT-MATTER', codes(structure.run(self.context())))

    def test_optional_by_position_count_mismatch(self):
        obj = self.settings()
        obj['registers'].append({'id': 'historical', 'label': 'Historical', 'required': False,
                                 'alignment': 'by-position', 'sections': ['historical translation']})
        profile = validate_profile(obj, 'positional.json')
        self.assertEqual(structure.run(self.context(profile)), [])
        with self.work_path.open('a') as handle:
            handle.write('\n## Historical translation\n### Own division\nHistorical text.\n')
        finding = next(f for f in structure.run(self.context(profile)) if f.code == 'SEG-PARITY')
        self.assertEqual(finding.rule, 'SEG-7')

    def test_blank_preservation_counts_each_blank(self):
        self.assertEqual(coverage.run(self.context()), [])
        target = self.work().register_section(self.profile(), 'plain').units[0].text
        self.change_text(target, target.replace('——', ''))
        blank = next(f for f in coverage.run(self.context()) if f.rule == 'SEG-9')
        self.assertEqual(blank.evidence, {'expected': 1, 'actual': 0})

    def test_short_unit_upper_middle_even_median_and_strict_boundary(self):
        original = [(f'U{i}', 's' * 100) for i in range(4)] + [('Tiny', 's' * 99)]
        musean = [(f'U{i}', 'm' * size) for i, size in enumerate((99, 100, 200, 300))] + [('Tiny', 'm')]
        plain = [(f'U{i}', 'p' * 400) for i in range(4)] + [('Tiny', 'p')]
        self.replace_units(original, musean, plain)
        ctx = self.context(self.profile(short_unit_ratio=.5, min_source_chars=100))
        found = [f for f in coverage.run(ctx) if f.code == 'VER-SHORT-UNIT']
        self.assertEqual([(f.unit, f.register) for f in found], [('U0', 'musean')])
        self.assertEqual(found[0].evidence, {'ratio': .99, 'median': 2.0, 'threshold': .5, 'eligible_units': 4})
        self.assertNotIn('U1', [f.unit for f in found])  # ratio 1 == .5 * upper median 2
        self.assertNotIn('Tiny', [f.unit for f in found])

    def test_short_unit_minimum_eligible_units_and_comment_stripping(self):
        original = [('A', 's' * 100), ('B', 's' * 100), ('C', 's' * 99 + '<!-- not counted -->')]
        musean = [('A', 'm'), ('B', 'm' * 100), ('C', 'm' * 100)]
        plain = [('A', 'p' * 100), ('B', 'p' * 100), ('C', 'p' * 100)]
        self.replace_units(original, musean, plain)
        ctx = self.context(self.profile(min_source_chars=100))
        self.assertEqual(coverage.run(ctx), [])
        status = next(g for g in coverage.statuses(ctx, []) if g['check'] == 'coverage.short_unit_ratio')
        self.assertEqual(status['status'], 'inapplicable')

    def test_disabled_ratio_visible_and_source_form_unsupported(self):
        self.record(source_form={'stanzas': 2})
        ctx = self.context(self.profile(short_unit_ratio=None))
        statuses = coverage.statuses(ctx, coverage.run(ctx))
        self.assertEqual(next(g['status'] for g in statuses if g['check'] == 'coverage.short_unit_ratio'), 'disabled')
        self.assertEqual(next(g['status'] for g in statuses if g['check'] == 'coverage.source_form'), 'unsupported')


class NumberingTests(ProjectCase):
    def test_all_supported_notations_extract_in_order_without_comment_markers(self):
        text = '1. A\n2.3 B\n[3.4] C (4.5) [page 7] ॥8॥ [17b] [Bekker 1447a line 8]\n999 D\n<!-- [18b] -->'
        self.assertEqual(numbering.extract_markers(text), ['1.', '2.3', '[3.4]', '(4.5)', '[page 7]', '॥8॥', '[17b]', '[Bekker 1447a line 8]', '999'])
        self.assertEqual(numbering.extract_markers('12.1 Text', 'N.N'), ['12.1'])
        with self.assertRaises(ChampollionError):
            numbering.extract_markers(text, 'unknown-runes')

    def test_order_missing_extra_and_duplicate_markers_not_just_counts(self):
        self.assertEqual(numbering.run(self.context()), [])
        for body, actual in [('2. B\n1. A', ['2.', '1.']), ('1. A', ['1.']),
                             ('1. A\n2. B\n3. C', ['1.', '2.', '3.']), ('1. A\n1. B', ['1.', '1.'])]:
            with self.subTest(body=body):
                self.replace_units([('One', '1. Source\n2. Source')], [('One', '1. Target\n2. Target')], [('One', body)])
                found = numbering.run(self.context())
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0].evidence['expected'], ['1.', '2.'])
                self.assertEqual(found[0].evidence['actual'], actual)

    def test_line_for_line_contract_with_equal_markers(self):
        self.record(numbering={'notation': 'leading-number', 'line_for_line': True})
        self.replace_units([('One', '1. Source\n2. Source')], [('One', '1. Target\n2. Target')], [('One', '1. Target\ncontinued\n2. Target')])
        found = numbering.run(self.context())
        self.assertEqual([f.rule for f in found], ['SEG-6'])
        self.assertEqual(found[0].evidence, {'expected': 2, 'actual': 3})

    def test_unsupported_and_absent_marker_evidence_never_passed(self):
        self.record(numbering={'notation': 'runes'})
        ctx = self.context()
        self.assertEqual(numbering.run(ctx), [])
        self.assertEqual(numbering.statuses(ctx, [])[0]['status'], 'unsupported')
        self.assertIn('runes', numbering.statuses(ctx, [])[0]['detail'])
        self.record(numbering={})
        self.replace_units([('One', 'Unnumbered source')], [('One', 'Target')], [('One', 'Other target')])
        ctx = self.context()
        self.assertEqual(numbering.statuses(ctx, [])[0]['status'], 'inapplicable')


class CopySpeechHygieneLanguageTests(ProjectCase):
    def test_copy_denominator_retains_repeated_plain_occurrences(self):
        shared = 'This deliberately shared sentence is long enough for the test.'
        unique = 'This separate target sentence contains different wording entirely.'
        self.replace_units([('One', 's' * 100)], [('One', shared)], [('One', '\n'.join([shared] * 3 + [unique]))])
        found = register.run(self.context(self.profile(copy_ratio=.5)))
        self.assertEqual(len(found), 1)
        expected = {'same': 3, 'total': 4, 'ratio': .75, 'threshold': .5, 'eligible_sentences': 4}
        self.assertEqual({key: found[0].evidence[key] for key in expected}, expected)
        self.assertEqual(found[0].evidence['reference_register'], 'musean')
        self.assertEqual(found[0].evidence['compared_register'], 'plain')
        self.assertEqual(found[0].rule, 'REG-3')

    def test_copy_exact_threshold_case_sensitivity_and_sentence_minima(self):
        shared = 'Shared eligible sentence.'
        self.replace_units([('One', 's' * 100)], [('One', shared)], [('One', '\n'.join([shared] * 2 + ['Different sentence with enough characters.'] * 2))])
        self.assertEqual(register.run(self.context(self.profile(copy_ratio=.5))), [])
        self.assertEqual(register.run(self.context(self.profile(copy_ratio=0, min_sentences=5))), [])
        self.replace_units([('One', 's' * 100)], [('One', shared.lower())], [('One', '\n'.join([shared] * 4))])
        self.assertEqual(register.run(self.context(self.profile(copy_ratio=0))), [])
        self.assertEqual(register.sentences('1234. 12345.\nabcde!\nfour', 6), ['12345.', 'abcde!'])

    def test_arbitrary_register_overlap_has_no_english_assumptions(self):
        shared = 'La lámpara ilumina la mesa durante toda la noche.'
        self.replace_units([('One', 'Lux mensam illuminat.')], [('One', shared)],
                           [('One', '\n'.join([shared] * 4))])
        obj = self.settings()
        obj['target'] = {'tag': 'es', 'name': 'Spanish'}
        obj['target_locale'] = 'es'
        for item, ident in zip(obj['registers'], ('literaria', 'clara')):
            item['id'] = ident
            item['label'] = ident.capitalize()
        obj['checks'].update(archaisms='off', plain_archaisms=False, spelling_profile=None,
                             name_table=None, speech_marks=[], copy_ratio=.5)
        profile = validate_profile(obj, 'spanish-overlap.json')
        ctx = self.context(profile)
        found = register.run(ctx)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].rule, 'REG-3')
        self.assertEqual(found[0].register, 'clara')
        self.assertEqual(found[0].evidence['ratio'], 1.0)
        self.assertEqual(found[0].evidence['reference_register'], 'literaria')
        self.assertEqual(found[0].evidence['compared_register'], 'clara')
        self.assertEqual(register.statuses(ctx, found)[0]['status'], 'failed')

    def test_speech_balanced_unclosed_nested_and_orphan_closing(self):
        for body, fragments in [('"A complete speech."', []), ('"Unclosed speech.', ['speech never closed']),
                                ('"First speech. "Second speech."', ['new speech opens']),
                                ('Orphan speech."', ['closing mark with no open speech'])]:
            with self.subTest(body=body):
                self.replace_units([('One', 'Source')], [('One', 'Target')], [('One', body)])
                found = speech.run(self.context())
                self.assertEqual(len(found), len(fragments))
                for fragment, f in zip(fragments, found): self.assertIn(fragment, f.message)
        ctx = self.context(work_scope={'iliad', 'odyssey'})
        self.assertEqual(speech.run(ctx), [])
        self.assertEqual(speech.statuses(ctx, [])[0]['status'], 'inapplicable')
        self.assertIn('iliad', speech.statuses(ctx, [])[0]['detail'])

    def test_speech_state_resets_per_unit_and_balances_across_lines(self):
        self.replace_units([('A', 'Source'), ('B', 'Source')], [('A', 'Target'), ('B', 'Target')],
                           [('A', '"Across\nlines."'), ('B', 'Orphan."')])
        found = speech.run(self.context())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].unit, 'B')

    def test_hygiene_each_code_and_reviewed_repetition_allowlist(self):
        self.assertEqual(hygiene.run(self.context()), [])
        self.replace_units([('One', 'Source')], [('One', 'Target')], [('One', '[OCR unclear] ^ bird bird ..')])
        found = hygiene.run(self.context())
        self.assertEqual(codes(found), ['VER-OCR-MARKER', 'VER-DEBRIS', 'VER-DOUBLED-WORD', 'VER-ELLIPSIS'])
        self.assertEqual(found[-1].severity, 'warn')
        found = hygiene.run(self.context(self.profile(ellipsis='error')))
        self.assertEqual(found[-1].severity, 'error')
        self.replace_units([('One', 'Source')], [('One', 'Target')], [('One', 'had had …\n<!-- ^ [OCR unclear] bird bird -->')])
        self.assertEqual(hygiene.run(self.context()), [])

    def test_three_dot_ellipsis_is_required_single_character(self):
        self.replace_units([('One', 'Source')], [('One', 'Target')], [('One', 'Text ... continues.')])
        found = hygiene.run(self.context(self.profile(ellipsis='error')))
        self.assertIn('VER-ELLIPSIS', codes(found), 'SPEC REG-9 requires one ellipsis character; legacy oracle limitation must not become core acceptance')

    def test_language_gates_exact_counts_and_house_scope(self):
        self.assertEqual(language.run(self.context()), [])
        self.replace_units([('One', 'Thou colour Hektor')], [('One', 'Behold the harbor.')],
                           [('One', 'Thou behold the colour of the harbour, Hektor and Hektor.')])
        found = language.run(self.context())
        self.assertEqual(codes(found), ['REG-ARCHAISM', 'REG-PLAIN-ARCHAISM', 'REG-SPELLING', 'REG-NAME-VARIANT'])
        self.assertEqual(next(f.evidence['count'] for f in found if f.code == 'REG-SPELLING'), 2)
        self.assertEqual(next(f.evidence['count'] for f in found if f.code == 'REG-NAME-VARIANT'), 2)
        self.assertTrue(all(f.register == 'plain' for f in found))

    def test_language_off_and_spanish_policy_reported_unsupported(self):
        profile = self.profile(archaisms='off', plain_archaisms=False, spelling_profile=None, name_table=None)
        self.assertEqual(language.run(self.context(profile)), [])
        self.assertEqual(language.statuses(self.context(profile), [])[0]['status'], 'disabled')
        obj = self.settings(); obj['target'] = {'tag': 'es', 'name': 'Spanish'}; obj['target_locale'] = 'es'
        obj['checks'].update(archaisms='off', plain_archaisms=False, spelling_profile='es', name_table=None)
        profile = validate_profile(obj, 'spanish.json')
        ctx = self.context(profile)
        self.assertEqual(language.run(ctx), [])
        self.assertEqual(language.statuses(ctx, [])[0]['status'], 'unsupported')
        with self.assertRaises(ChampollionError) as caught: self.report(profile)
        self.assertEqual(caught.exception.cause, 'unsupported-language-policy')

    def test_name_table_missing_invalid_and_path_escape_are_named(self):
        for value in ('missing.json', '../outside.json'):
            with self.subTest(value=value), self.assertRaises(ChampollionError):
                language.run(self.context(self.profile(name_table=value)))
        (self.root / 'names.json').write_text('{"synthetic": {"Hektor": "Hector", "Hektor": "Other"}}')
        with self.assertRaises(ChampollionError): language.run(self.context())


class ProvenanceRightsTests(ProjectCase):
    def test_provenance_pass_and_each_required_key_missing(self):
        self.assertEqual(provenance.run(self.context()), [])
        for key in provenance.BASE_KEYS + ('musean_translator', 'musean_note', 'plain_translator', 'plain_note'):
            ctx = self.context()
            ctx.work.front.pop(key)
            with self.subTest(key=key):
                found = provenance.run(ctx)
                self.assertEqual([f.evidence['key'] for f in found], [key])
                self.assertEqual(codes(found), ['PRV-INCOMPLETE'])

    def test_invalid_provenance_values_are_not_coerced(self):
        invalid = {'slug': 'Upper', 'language': 'bad_tag', 'source_url': 'moving page',
                   'raw_snapshot': '../outside', 'source': 'https://example.invalid/source',
                   'completeness': 'partial', 'source_scope': 'excerpt', 'as_of': '2026-02-30'}
        for key, value in invalid.items():
            ctx = self.context(); ctx.work.front[key] = value
            with self.subTest(key=key):
                self.assertIn(key, [f.evidence['key'] for f in provenance.run(ctx)])

    def test_rights_hash_pin_provider_and_missing_snapshot(self):
        self.assertEqual(rights.run(self.context()), [])
        for changes, expected in [({'revision': 'HEAD'}, 'SRC-NO-PIN'), ({'provider': ''}, 'SRC-7'),
                                  ({'rights': {'work': 'CC0-1.0', 'transcription': 'unknown'}}, 'SRC-RIGHTS'),
                                  ({'sha256': '0' * 64}, 'SRC-HASH-MISMATCH'), ({'sha256': None}, 'SRC-8'),
                                  ({'raw_snapshot': 'sources/raw/missing.txt'}, 'SRC-8')]:
            with self.subTest(changes=changes):
                ctx = self.context()
                source = copy.deepcopy(ctx.sources['synthetic']); source.update(changes)
                ctx.sources = {'synthetic': source}
                self.assertIn(expected, codes(rights.run(ctx)))
        ctx = self.context(); ctx.sources = {}
        self.assertEqual(codes(rights.run(ctx)), ['SRC-8'])
        self.assertEqual(rights.statuses(ctx, rights.run(ctx))[0]['status'], 'failed')

    def test_byte_hash_uses_snapshot_bytes_including_crlf(self):
        raw = self.root / 'sources/raw/synthetic.txt'
        raw.write_bytes(raw.read_bytes().replace(b'\n', b'\r\n'))
        mismatch = next(f for f in rights.run(self.context()) if f.code == 'SRC-HASH-MISMATCH')
        self.assertNotEqual(mismatch.evidence['expected_sha256'], mismatch.evidence['computed_sha256'])

    def test_unknown_or_missing_separate_rights_never_publication_eligible(self):
        self.record(rights='CC0-1.0')
        report = self.report()
        self.assertEqual(report['publication_gate']['status'], 'blocked')
        gate = next(g for g in report['works'][0]['gates'] if g['check'] == 'rights.separation')
        self.assertEqual(gate['status'], 'unsupported')

    def test_source_path_traversal_and_malformed_records_named(self):
        for obj in ([], {}, {'records': {}}, {'records': [False]}, {'records': [{}]},
                    {'records': [{'id': 'x'}, {'id': 'x'}]}):
            with self.subTest(obj=obj):
                write_json(self.root / 'sources/manifest.json', obj)
                with self.assertRaises(ChampollionError) as caught: self.report()
                self.assertIn('manifest.json', str(caught.exception))
        (self.root / 'sources/manifest.json').write_text('{"records": [], "records": []}')
        with self.assertRaises(ChampollionError): self.report()
        write_json(self.root / 'sources/manifest.json', {'records': []})
        self.change_text('sources/manifest.json#synthetic', '../outside.json#synthetic')
        with self.assertRaises(ChampollionError) as caught: self.report()
        self.assertIn('outside project root', str(caught.exception))


class ExceptionReportTests(ProjectCase):
    def exception_profile(self, code='REG-ARCHAISM', unit='One', expires='2026-01-03'):
        obj = self.settings()
        obj['exceptions'] = [{'code': code, 'work': 'synthetic', 'unit': unit, 'owner': 'synthetic owner',
                              'reason': 'Synthetic test only', 'recorded': '2026-01-01', 'expires': expires}]
        return validate_profile(obj, 'exception.json')

    def setUp(self):
        super().setUp()
        self.replace_units([('One', 'Source')], [('One', 'Target')], [('One', 'Thou returnest.')])

    def test_matched_exception_warn_visible_and_exact_expiry_not_overdue(self):
        report = self.report(self.exception_profile(), today='2026-01-03')
        row = next(r for r in report['findings'] if r['code'] == 'REG-ARCHAISM')
        self.assertEqual(row['severity'], 'error')
        self.assertEqual(row['effective_severity'], 'warn')
        self.assertTrue(report['exceptions'][0]['matched'])
        self.assertTrue(report['exceptions'][0]['applied'])
        self.assertFalse(report['exceptions'][0]['overdue'])
        self.assertIn('WARN synthetic [One] REG-ARCHAISM:', render_text(report))
        self.assertIn('[exception]', render_text(report))
        self.assertEqual(report['counts']['warnings'], 1)

    def test_overdue_restores_blocking_and_unmatched_debt_is_visible(self):
        report = self.report(self.exception_profile(expires='2026-01-02'), today='2026-01-03')
        self.assertIn('VER-12', [r['code'] for r in report['findings']])
        self.assertEqual(report['counts']['overdue'], 1)
        self.assertFalse(report['exceptions'][0]['applied'])
        report = self.report(self.exception_profile(unit='one'))
        self.assertFalse(report['exceptions'][0]['matched'])
        self.assertEqual(report['counts']['unmatched_exceptions'], 1)
        self.assertEqual(report['counts']['exception_debt'], 1)
        self.assertGreater(report['counts']['errors'], 0)

    def test_source_exception_cannot_make_unknown_rights_admissible(self):
        self.record(rights={'work': 'CC0-1.0', 'transcription': 'unknown'})
        profile = self.exception_profile(code='SRC-RIGHTS', unit='work-level')
        report = self.report(profile)
        row = next(r for r in report['findings'] if r['code'] == 'SRC-RIGHTS')
        self.assertEqual(row['effective_severity'], 'error')
        self.assertFalse(report['exceptions'][0]['applied'])

    def test_reports_deterministic_and_check_has_no_writes(self):
        before = tree_state(self.root)
        first = self.report()
        second = self.report()
        self.assertEqual(first, second)
        self.assertEqual(tree_state(self.root), before)
        self.assertEqual(json.loads(render_text(first, json_mode=True)), first)
        self.assertEqual(first['run_date'], TODAY)
        self.assertTrue(first['profile']['fingerprint'].startswith('sha256:'))
        self.assertIn('expected_sha256', first['works'][0]['source'])
        self.assertIn('computed_sha256', first['works'][0]['source'])
        self.assertFalse(first['incomplete'])
        self.assertEqual(first['publication_gate']['status'], 'blocked')

    def test_missing_review_kept_separate_and_bad_review_schema_refused(self):
        report = self.report()
        self.assertEqual(report['judgement']['review_records'], [])
        self.assertTrue(any('VER-11' in b for b in report['works'][0]['publication_gate']['blockers']))
        self.record(reviews=[{'reviewer': 'not a complete record'}])
        with self.assertRaises(ChampollionError) as caught: self.report()
        self.assertEqual(caught.exception.cause, 'VER-11')


if __name__ == '__main__':
    unittest.main()
