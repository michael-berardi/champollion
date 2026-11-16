import copy
import json
import unittest
from unittest.mock import patch
from pathlib import Path

from champollion.summary import basis_hash, section_units, validate, word_count, _normalise_passage
from tests import test_summary


class Summary170Tests(unittest.TestCase):
    def setUp(self):
        base = test_summary.SummaryTests('test_cli'); base.setUp()
        self.work, self.profile, self.obj = base.work, base.profile, copy.deepcopy(base.obj)
        for idea in self.obj['summary']['key_ideas']: idea['explanation'] += '.'
        for unit in self.obj['summary']['units']: unit['summary'] += '.'

    def findings(self, **kwargs):
        return validate(self.obj, self.work, self.profile, {'example', 'other'}, **kwargs)

    def test_word_count(self):
        self.assertEqual(word_count('漢字 hello 123 !'), 4)

    def test_freshness_and_language(self):
        self.obj['basis']['unit_sha256'] = [basis_hash(t) for _, _, t in section_units(self.work, 'plain', self.profile)]
        self.obj['basis']['unit_sha256'][1] = 'bad'
        self.obj['basis']['sha256'] = 'bad'
        self.obj['edition_source_sha256'] = 'bad'
        self.work.front['source_sha256'] = 'source'
        f = self.findings(lang='en')
        self.assertTrue(any('units 2 changed' in x.message for x in f))
        self.assertTrue(any('edition_source_sha256' in x.message for x in f))
        self.assertTrue(any('lang: does not match edition' in x.message for x in f))

    def test_blurb(self):
        for text in ('a' * 161 + '.', '漢' * 81 + '。'):
            self.obj['summary']['blurb'] = text
            self.assertTrue(any(x.code == 'SUM-LENGTH' for x in self.findings()))

    def test_endings(self):
        for ending in ('…', '...', ',', ';', ':', '，', '；', '：', '、', '—', '–'):
            self.obj['summary']['gist'] = 'Text' + ending
            self.assertTrue(any(x.code == 'SUM-TRUNCATED' and 'gist' in x.message for x in self.findings()), ending)
        self.obj['summary']['gist'] = 'He said “text...”'
        self.assertFalse(any(x.code == 'SUM-TRUNCATED' and 'gist' in x.message for x in self.findings()))

    def test_markup(self):
        self.assertEqual(_normalise_passage('1. The way is *not* hard\n2. If only you do not choose.'), 'The way is not hard If only you do not choose.')
        self.obj['summary']['passages'][0]['text'] = '*quoted*'
        self.assertTrue(any('contains markup' in x.message for x in self.findings()))

    def test_numbered_passage_and_emphasis(self):
        units = section_units(self.work, 'plain', self.profile)
        units[1] = (2, 'First', '1. The way is *not* hard\n2. If only you do not choose.')
        self.obj['summary']['passages'][0]['text'] = 'The way is not hard If only you do not choose.'
        with patch('champollion.summary.section_units', return_value=units):
            self.assertFalse(any(x.code == 'SUM-PASSAGE' for x in self.findings()))

    def test_hash_listing_and_empty_idea(self):
        units = [(i, '', str(i)) for i in range(1, 16)]
        self.obj['basis']['unit_sha256'] = ['bad'] * 15
        self.obj['summary']['key_ideas'][0]['units'] = []
        with patch('champollion.summary.section_units', return_value=units):
            findings = self.findings()
        self.assertTrue(any('units 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 +3 more changed' in f.message for f in findings))
        self.assertTrue(any(f.code == 'SUM-XREF' and f.severity == 'warn' for f in findings))

    def test_fixture_truncation(self):
        self.obj['summary']['gist'] = 'Unfinished,'
        self.assertTrue(any(x.code == 'SUM-TRUNCATED' for x in self.findings()))

    def test_sentence_fields_must_end_a_sentence(self):
        self.obj['summary']['units'][0]['summary'] = 'No closing stop'
        self.assertTrue(any(x.code == 'SUM-TRUNCATED' and 'does not end a sentence' in x.message for x in self.findings()))
        self.obj['summary']['units'][0]['summary'] = 'She asks, "Is it time?"'
        self.obj['summary']['key_ideas'][0]['title'] = 'A title without a stop'
        self.assertFalse(any(x.code == 'SUM-TRUNCATED' for x in self.findings()))

    def test_good_blurb_and_plain_number_quote(self):
        self.obj['summary']['blurb'] = 'A short account of what the work says.'
        self.assertEqual([x for x in self.findings() if x.severity == 'error'], [])
        self.obj['summary']['blurb'] = 'No closing stop'
        self.assertTrue(any(x.code == 'SUM-TRUNCATED' and 'blurb' in x.message for x in self.findings()))
        units = section_units(self.work, 'plain', self.profile)
        units[1] = (2, 'First', '1776 was the year. [12] It changed much.')
        with patch('champollion.summary.section_units', return_value=units):
            self.obj['summary']['blurb'] = 'A short account.'
            self.obj['summary']['passages'][0]['text'] = '1776 was the year. It changed much.'
            self.assertFalse(any(x.code == 'SUM-PASSAGE' for x in self.findings()))
            self.obj['summary']['passages'][0]['text'] = '1. The year.'
            self.assertTrue(any('contains markup' in x.message for x in self.findings()))

    def test_fixture_file(self):
        obj = json.loads((Path(__file__).parent / 'fixtures/summary/SUM-TRUNCATED.json').read_text())
        self.assertIn('SUM-TRUNCATED', {f.code for f in validate(obj, self.work, self.profile, {'example', 'other'})})

    def test_cjk_and_word_boundaries(self):
        from champollion.summary import _contains_run
        self.assertTrue(_contains_run('子曰學而時習之不亦說乎', '學而時習之'))
        self.assertTrue(_contains_run('The way is not hard.', 'way is not'))
        self.assertFalse(_contains_run('The highway is not hard.', 'way is not'))
        self.assertFalse(_contains_run('The way is nothing.', 'way is not'))

    def test_guillemets_and_superscript_note_calls(self):
        self.obj['summary']['gist'] = 'Cierra con «¡Uníos!»'
        self.assertFalse(any(x.code == 'SUM-TRUNCATED' and 'gist' in x.message for x in self.findings()))
        self.assertEqual(_normalise_passage('Zadig blessed heaven\u1d43. Next'), 'Zadig blessed heaven. Next')

    def test_public_helpers(self):
        from champollion.summary import clean_quote, ending_problem, passage_in, passage_key, blurb_limit, quote_markup
        self.assertEqual(clean_quote('1. The *way* is [12] not hard\n2. If only [B 443] you _choose_ .'), 'The way is not hard If only you choose.')
        self.assertFalse(quote_markup(clean_quote('**Act** so that [^n1] you [Bekker 1094a line 3] use humanity.')))
        self.assertEqual(clean_quote('He wrote [sic] in 1776 that I [the king] rule.'), 'He wrote [sic] in 1776 that I [the king] rule.')
        self.assertEqual(ending_problem('A clause;'), 'ends cut off')
        self.assertEqual(ending_problem('A title'), '')
        self.assertEqual(ending_problem('A title', True), 'does not end a sentence')
        self.assertEqual(ending_problem('結束了。', True), '')
        self.assertEqual(ending_problem('He ends: "and so..."', True), '')
        self.assertTrue(passage_in('pure reason is practical. So it is.', 'Now *pure reason* is practical. [AA V 31] So it is.'))
        self.assertFalse(passage_in('Pure reason is not practical.', 'Now *pure reason* is practical.'))
        self.assertEqual(passage_key('[1.2] One [1807 xii] two'), 'One two')
        self.assertEqual((blurb_limit('漢字漢字 a'), blurb_limit('Latin text 漢')), (80, 160))

