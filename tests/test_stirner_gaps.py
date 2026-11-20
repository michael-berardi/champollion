"""Gaps found adding the 1845 Stirner edition to Mouseia: author notes, word-bounded
packets, DTA extraction helpers, and vendored bytecode caches."""
import json
from pathlib import Path
import shutil
import sys
import unittest

sys.dont_write_bytecode = True

from champollion import chunking
from champollion.checks import hygiene
from champollion.dta import join_hyphen_signs, page_label
from champollion.export.typeset import _emphasis_html
from champollion.findings import ChampollionError
from champollion.notes import anchors, mask_marks, note_labels, paired_labels
from champollion.profile import validate_profile
from champollion.vendor import vendor, verify_vendor
from tests.fixtures.support import FIXTURES, TODAY, ProjectCase, codes, tree_state
from tests.test_tooling import CliCase

PACKETS = FIXTURES / 'packets'


class AuthorNoteTests(ProjectCase):
    def test_star_labels_are_whole_tokens(self):
        lines = ['Text one.*) Text two.**) Three.***)', '[Note *)] a', '[Note **)] b']
        self.assertEqual(note_labels(lines), ['*)', '**)'])
        self.assertEqual(anchors(lines, ['*)', '**)']), ['*)', '**)'])
        self.assertEqual(paired_labels(lines), {'*)', '**)'})
        self.assertEqual(paired_labels(['Text.**)', '[Note *)] a']), set(), '*) must not match inside **)')
        self.assertEqual(anchors(['See (a) and (b).', '[Note (a)] x'], ['(a)']), ['(a)'])
        self.assertEqual(mask_marks('[Note **)] b **bold**', {'**)'}), '[Note    ] b **bold**')

    def test_paired_marks_pass_and_unpaired_marks_remain_debris(self):
        notes = 'Text.*) More text.**)\n[Note *)] First note.\n[Note **)] Second note.'
        self.replace_units([('One', notes)], [('One', notes)], [('One', notes)])
        self.assertEqual(hygiene.run(self.context()), [])
        # A dropped note line leaves its anchor unpaired: still VER-DEBRIS.
        self.replace_units([('One', notes)], [('One', notes)], [('One', 'Text.*) More text.**)\n[Note *)] First note.')])
        found = hygiene.run(self.context())
        self.assertEqual(codes(found), ['VER-DEBRIS'])
        self.assertIn("'**'", found[0].message)
        # A note line whose anchor was dropped is also unpaired.
        self.replace_units([('One', notes)], [('One', notes)], [('One', 'Text.*) More text.\n[Note *)] One.\n[Note **)] Two.')])
        self.assertEqual(codes(hygiene.run(self.context())), ['VER-DEBRIS'])
        # Pairing exempts only the mark: other markup on the same line is still debris.
        self.replace_units([('One', notes)], [('One', notes)], [('One', 'Text **bold**.**)\n[Note **)] Two.')])
        self.assertEqual(codes(hygiene.run(self.context())), ['VER-DEBRIS'])
        # Pairing is per unit, not across units.
        self.replace_units([('A', 'x'), ('B', 'y')], [('A', 'x'), ('B', 'y')],
                           [('A', 'Text.**)'), ('B', '[Note **)] Two.')])
        self.assertEqual(codes(hygiene.run(self.context())), ['VER-DEBRIS', 'VER-DEBRIS'])

    def test_escaped_marks_are_not_the_supported_form(self):
        self.replace_units([('One', 'x')], [('One', 'x')], [('One', 'Text.\\*\\*)\n[Note \\*\\*)] Two.')])
        self.assertEqual(codes(hygiene.run(self.context())), ['VER-DEBRIS', 'VER-DEBRIS'])

    def test_non_english_neutral_debris_also_respects_pairs(self):
        settings = self.settings()
        settings.update(target={'tag': 'de', 'name': 'German'}, target_locale=None)
        settings['checks'].update(archaisms='off', plain_archaisms=False, spelling_profile=None, name_table=None)
        profile = validate_profile(settings, 'synthetic.json')
        self.replace_units([('One', 'x')], [('One', 'Text.**)\n[Note **)] Zwei.')], [('One', 'Text.**)')])
        self.assertEqual(codes(hygiene.run(self.context(profile))), ['VER-DEBRIS'])

    def test_inline_emphasis_does_not_pair_note_marks(self):
        self.assertEqual(_emphasis_html('One.*) Two.*) Three'), 'One.*) Two.*) Three')
        self.assertEqual(_emphasis_html('One.**) Two.**)'), 'One.**) Two.**)')
        self.assertEqual(_emphasis_html('*Ich* and **Eigner**.*)'), '<em>Ich</em> and <strong>Eigner</strong>.*)')


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.text = (PACKETS / 'original.md').read_text(encoding='utf-8')

    def test_split_keeps_headings_markers_and_notes_with_their_blocks(self):
        packets = chunking.split_text(self.text, 50)
        self.assertEqual(len(packets), 4)
        self.assertTrue(packets[0].startswith('# First Part\n\n## The Garden\n\n[1845 1]\n\n[GDN 0001]'))
        self.assertTrue(packets[0].rstrip().endswith('rule of the garden.'))
        self.assertTrue(packets[2].startswith('## The Well') and '[Note **)]' in packets[2])
        self.assertTrue(packets[3].startswith('[1845 3]\n\n[GDN 0004]'))
        for packet in packets[1:]:
            self.assertLessEqual(len(packet.split()), 50)

    def test_join_of_split_is_the_normalized_original(self):
        for limit in (1, 20, 50, 10_000):
            packets = chunking.split_text(self.text, limit)
            self.assertEqual('\n\n'.join(p.strip() for p in packets) + '\n', chunking.normalized(self.text))
        self.assertEqual(len(chunking.split_text(self.text, 10_000)), 1)
        for bad in (0, -1, 2.5):
            with self.assertRaises(ChampollionError):
                chunking.split_text(self.text, bad)


class PacketVerifyTests(CliCase):
    def split(self, limit=50):
        out = Path(self.temp.name) / 'source-packets'
        return out, chunking.write_split(str(PACKETS / 'original.md'), str(out), limit)

    def test_fixture_drafts_report_each_dropped_and_reordered_item(self):
        source, manifest = self.split()
        self.assertEqual([p['file'] for p in manifest['packets']], ['001.md', '002.md', '003.md', '004.md'])
        result = chunking.verify_packets(str(source), str(PACKETS / 'drafts'))
        self.assertFalse(result['valid'])
        failed = {p['file']: p['problems'] for p in result['failed']}
        self.assertEqual(sorted(failed), ['003.md', '004.md'])
        self.assertEqual(failed['003.md'], ['notes: missing **)'])
        self.assertEqual(failed['004.md'], ['anchors: out of order at 1: expected [GDN 0004], found [GDN 0005]',
                                            'page markers: missing [1845 3]'])

    def test_missing_extra_duplicate_headings_files_and_inline_anchor(self):
        source, _ = self.split()
        drafts = Path(self.temp.name) / 'drafts'
        shutil.copytree(source, drafts)
        (drafts / 'packets.json').unlink()
        self.assertTrue(chunking.verify_packets(str(source), str(drafts))['valid'], 'identical packets verify')
        one = (drafts / '001.md').read_text()
        (drafts / '001.md').write_text(one.replace('## The Garden\n\n', '').replace('behind.*)', 'behind.')
                                       .replace('[1845 1]', '[1845 1] [1845 1] [1845 9]') + '\n[GDN 0099] Extra.\n')
        (drafts / '002.md').unlink()
        (drafts / '005.md').write_text('[GDN 0006] Stray.\n')
        result = chunking.verify_packets(str(source), str(drafts))
        failed = {p['file']: p['problems'] for p in result['failed']}
        self.assertEqual(failed['001.md'], [
            'anchors: extra [GDN 0099]',
            'page markers: duplicate [1845 1] (2 for 1)', 'page markers: extra [1845 9]',
            'headings: 1 in draft, 2 in source',
            'notes: inline anchor *) missing from draft text'])
        self.assertEqual(failed['002.md'], ['draft missing'])
        self.assertEqual(failed['005.md'], ['draft has no source packet'])
        self.assertEqual(result['problems'], 7)

    def test_custom_patterns_and_invalid_pattern(self):
        source, _ = self.split()
        result = chunking.verify_packets(str(source), str(PACKETS / 'drafts'), anchor=r'^\[GDN 000[0-3]\]')
        failed = {p['file']: p['problems'] for p in result['failed']}
        self.assertEqual(failed['004.md'], ['page markers: missing [1845 3]'])
        with self.assertRaises(ChampollionError) as caught:
            chunking.verify_packets(str(source), str(PACKETS / 'drafts'), page='[')
        self.assertEqual(caught.exception.cause, 'usage')

    def test_cli_split_verify_join_and_refusals(self):
        out = Path(self.temp.name) / 'cli-split'
        result = self.checked('packets', 'split', PACKETS / 'original.md', '--max-words', '50', '--out', out, '--json')
        self.assertEqual(len(result['packets']), 4)
        before = tree_state(out)
        self.checked('packets', 'split', PACKETS / 'original.md', '--max-words', '50', '--out', out, '--json')
        self.assertEqual(tree_state(out), before, 'rerun with identical bytes is a no-op')
        status, _, errors = self.cli('packets', 'split', PACKETS / 'original.md', '--max-words', '20', '--out', out)
        self.assertEqual(status, 2)
        self.assertIn('existing file differs', errors)
        status, output, _ = self.cli('packets', 'verify', out, PACKETS / 'drafts')
        self.assertEqual(status, 1)
        self.assertIn('004.md: page markers: missing [1845 3]', output)
        self.assertIn('4 packets, 2 failed, 3 problems', output)
        status, output, _ = self.cli('packets', 'verify', out, PACKETS / 'drafts', '--json')
        self.assertEqual((status, json.loads(output)['valid']), (1, False))
        joined = Path(self.temp.name) / 'joined.md'
        status, _, errors = self.cli('packets', 'join', PACKETS / 'drafts', '--source', out, '--out', joined)
        self.assertEqual(status, 2)
        self.assertIn('WRK-5', errors)
        self.assertFalse(joined.exists())
        result = self.checked('packets', 'join', out, '--source', out, '--out', joined, '--json')
        self.assertTrue(result['verified'])
        self.assertEqual(joined.read_text(encoding='utf-8'),
                         chunking.normalized((PACKETS / 'original.md').read_text(encoding='utf-8')))
        status, _, errors = self.cli('packets', 'join', out, '--out', out / 'joined.md')
        self.assertEqual(status, 2)

    def test_unit_packets_still_require_register_and_units(self):
        status, _, errors = self.cli('packets', '--root', self.root, '--units', '1-2')
        self.assertEqual(status, 2)
        self.assertIn('usage: packets requires --register and --units', errors)
        result = self.checked('packets', '--root', self.root, '--register', 'plain', '--units', '1-1', '--json')
        self.assertEqual(len(result['packets']), 1)


class DtaTests(unittest.TestCase):
    def test_page_label_prefers_the_supplied_number(self):
        self.assertEqual([page_label(n) for n in ('35 [354]', '[iv]', ' 12 ', '38 [388]')], ['354', 'iv', '12', '388'])

    def test_hyphen_signs_across_emphasis_pages_and_note_anchors(self):
        cases = [
            ('Ueber¬ zeugung ist', 'Ueberzeugung ist'),
            ('die *Ueber*¬ *zeugung* ist', 'die *Ueberzeugung* ist'),
            ('*das Ueber*¬ *zeugte und*', '*das Ueberzeugte und*'),
            ('*Ke*i¬ *ner* weiß', '*Keiner* weiß'),
            ('die *Bie¬* nen fliegen', 'die *Bienen* fliegen'),
            ('Wort¬ [1845 35] fort', '[1845 35] Wortfort'),
            ('per¬ *) [1845 347] ſönliche Sache', '[1845 347] perſönliche *) Sache'),
            ("Proud'¬ hon", "Proud'hon"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(join_hyphen_signs(raw), (expected, []))

    def test_unresolved_cases_are_residuals_not_guesses(self):
        text, residuals = join_hyphen_signs('*Geiſtig*¬ keit und Sätze¬ „so“')
        self.assertEqual(text, '*Geiſtig*keit und Sätze¬ „so“')
        self.assertEqual(residuals[0], '*Geiſtig*keit')
        self.assertIn('Sätze¬', residuals[1])


class VendorBytecodeTests(CliCase):
    def test_stale_pycache_is_reported_not_an_integrity_failure(self):
        destination = Path(self.temp.name) / 'vendor'
        package = Path(vendor(str(destination), today=TODAY)['directory'])
        cache = package / 'checks' / '__pycache__'
        cache.mkdir()
        (cache / 'hygiene.cpython-311.pyc').write_bytes(b'stale bytecode')
        (package / '__pycache__').mkdir()
        (package / '__pycache__' / 'removed_module.cpython-39.pyc').write_bytes(b'orphan')
        report = verify_vendor(str(destination))
        self.assertTrue(report['valid'], report)
        self.assertEqual(report['bytecode'], ['__pycache__/removed_module.cpython-39.pyc',
                                              'checks/__pycache__/hygiene.cpython-311.pyc'])
        status, output, errors = self.cli('verify-vendor', destination)
        self.assertEqual((status, errors), (0, ''))
        self.assertIn('ignored 2 __pycache__ bytecode file(s)', output)

    def test_other_files_in_pycache_and_loose_bytecode_stay_untracked(self):
        destination = Path(self.temp.name) / 'vendor'
        package = Path(vendor(str(destination), today=TODAY)['directory'])
        (package / '__pycache__').mkdir()
        (package / '__pycache__' / 'notes.txt').write_text('not bytecode')
        (package / 'loose.pyc').write_bytes(b'sourceless module')
        (package / '__pycache__' / 'nested').mkdir()
        (package / '__pycache__' / 'nested' / 'x.pyc').write_bytes(b'nested')
        report = verify_vendor(str(destination))
        self.assertFalse(report['valid'])
        self.assertEqual(report['extra'], ['__pycache__/nested/x.pyc', '__pycache__/notes.txt', 'loose.pyc'])
        (package / 'findings.py').write_text('# changed\n')
        self.assertIn('findings.py', verify_vendor(str(destination))['mismatches'])


if __name__ == '__main__':
    unittest.main()
