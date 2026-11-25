"""Synthetic pipe tables and `[^key]` source notes in printed books; no historical passages.

The defect these cases pin down: an edition body that prints a table or a named
source note reached the PDF and EPUB as the source's markup. A table arrived as
literal pipe rows, and a note call arrived as `[^323-1]` inside the sentence while
its printed definition arrived as a paragraph beginning `[^323-1]:`. Both are
source syntax, not reading text.
"""
import unittest

from champollion.export.epub import EPUB_CSS
from champollion.export.refs import parse_body
from champollion.export.typeset import Options, render_blocks

NOTE_CALL = '[^323-1]'
NOTE_BODY = 'The table is taken from a lecture draft.'
NOTE_DEF = NOTE_CALL + ': ' + NOTE_BODY
TABLE = ('| | 1. | |\n'
         '|---|---|---|\n'
         '| | *Der Quantität nach* | |\n'
         '| | Allgemeine | |')


class TableExportTests(unittest.TestCase):
    def render(self, text, lang='de', emphasis=True):
        return render_blocks(parse_body(text), lang, Options(inline_emphasis=emphasis))

    def test_table_rows_print_as_a_table_not_as_pipes(self):
        html = self.render(TABLE)
        self.assertIn('<table class="tbl">', html)
        self.assertNotIn('|', html)
        self.assertNotIn('---', html)

    def test_divider_row_marks_the_first_row_as_header(self):
        html = self.render(TABLE)
        self.assertIn('<thead><tr><th></th><th>1.</th><th></th></tr></thead>', html)
        self.assertIn('<tbody>', html)
        # The header appears once: the divider row is structural, not a printed row.
        self.assertEqual(html.count('<th>'), 3)

    def test_table_without_divider_has_no_header(self):
        html = self.render('| Satz | Gegensatz |\n| Welt | Natur |')
        self.assertNotIn('<thead>', html)
        self.assertNotIn('<th>', html)
        self.assertEqual(html.count('<td>'), 4)

    def test_cells_keep_source_emphasis_and_are_escaped(self):
        html = self.render('| Satz | Gegensatz |\n|---|---|\n| Die Welt hat einen *Anfang* | <img src=x onerror=alert(1)> |')
        self.assertIn('<th>Satz</th>', html)
        self.assertIn('<em>Anfang</em>', html)
        self.assertIn('&lt;img src=x', html)
        self.assertNotIn('<img ', html)

    def test_cells_render_named_note_calls_and_preserve_author_star_marks(self):
        html = self.render('| Claim | Mark |\n|---|---|\n| Entry[^323-1] | See *) and *) |')
        self.assertIn('<td>Entry<sup class="fn">323-1</sup></td>', html)
        self.assertIn('<td>See *) and *)</td>', html)
        self.assertNotIn('[^323-1]', html)

    def test_emphasis_is_literal_when_the_option_is_off(self):
        html = self.render(TABLE, emphasis=False)
        self.assertIn('<td>*Der Quantität nach*</td>', html)

    def test_ragged_rows_are_padded_to_the_widest_row(self):
        html = self.render('| a | b |\n|---|---|\n| one |\n| one | two | three |')
        body = html.split('<tbody>')[1]
        self.assertEqual({row.count('<td>') for row in body.split('<tr>')[1:]}, {3})

    def test_table_is_a_block_of_its_own_with_no_unit_reference(self):
        blocks = parse_body('[1] Lead.\n\n' + TABLE + '\n\n[2] After.')
        kinds = [block.kind for block in blocks]
        self.assertEqual(kinds, ['text', 'table', 'text'])
        self.assertEqual(blocks[1].ref, '')
        self.assertEqual([block.ref for block in blocks if block.kind == 'text'], ['1', '2'])

    def test_english_cells_get_smart_quotes_and_no_markup_leaks(self):
        html = self.render('| Satz | Gegensatz |\n|---|---|\n| "world" | -- |', lang='en')
        self.assertIn('\u201cworld\u201d', html)
        self.assertNotIn('|', html)

    def test_escaped_pipes_stay_inside_the_cell(self):
        html = self.render(r'| a \| b | c |' + '\n|---|---|\n' + r'| left \| right | end |')
        self.assertIn('<thead><tr><th>a | b</th><th>c</th></tr></thead>', html)
        self.assertIn('<tbody><tr><td>left | right</td><td>end</td></tr></tbody>', html)
        self.assertEqual(html.count('<th>'), 2)
        self.assertEqual(html.count('<td>'), 2)
        self.assertNotIn('\\', html)

    def test_divider_rows_at_other_positions_are_dropped_without_creating_a_header(self):
        html = self.render('|---|---|\n| a | b |\n|---|---|')
        self.assertNotIn('<thead>', html)
        self.assertNotIn('---', html)
        self.assertEqual(html.count('<td>'), 2)
        self.assertIn('<td>a</td><td>b</td>', html)

    def test_epub_stylesheet_defines_table_and_note_styles(self):
        self.assertIn('.tbl{', EPUB_CSS)
        self.assertIn('.note{', EPUB_CSS)


class NamedNoteExportTests(unittest.TestCase):
    def render(self, text, lang='de'):
        return render_blocks(parse_body(text), lang, Options())

    def test_call_becomes_a_superscript_and_definition_a_note_paragraph(self):
        html = self.render('A claim in the text.' + NOTE_CALL + '\n\n' + NOTE_DEF)
        self.assertIn('<sup class="fn">323-1</sup>', html)
        self.assertIn('<p class="note"><sup class="fn">323-1</sup> ' + NOTE_BODY + '</p>', html)
        self.assertNotIn('[^', html)

    def test_definition_inside_one_paragraph_keeps_its_continuation(self):
        html = self.render('[^12-3]: First part\ncontinues here.')
        self.assertIn('First part continues here.', html)
        self.assertNotIn('[^', html)

    def test_consecutive_definitions_in_one_paragraph_split_into_separate_notes(self):
        html2 = self.render('[^a]: First.\n[^b]: Second.')
        self.assertEqual(html2.count('<p class="note">'), 2)
        self.assertIn('<p class="note"><sup class="fn">a</sup> First.</p>', html2)
        self.assertIn('<p class="note"><sup class="fn">b</sup> Second.</p>', html2)

        html3 = self.render('[^a]: One.\n[^b]: Two.\n[^c]: Three.')
        self.assertEqual(html3.count('<p class="note">'), 3)
        self.assertIn('<p class="note"><sup class="fn">c</sup> Three.</p>', html3)

    def test_continued_definition_followed_by_another_definition(self):
        html = self.render('[^a]: First line\ncontinued here.\n[^b]: Second note.')
        self.assertEqual(html.count('<p class="note">'), 2)
        self.assertIn('<p class="note"><sup class="fn">a</sup> First line continued here.</p>', html)
        self.assertIn('<p class="note"><sup class="fn">b</sup> Second note.</p>', html)

    def test_several_calls_to_one_definition_all_print(self):
        html = self.render('One' + NOTE_CALL + ' two' + NOTE_CALL + '\n\n' + NOTE_DEF)
        self.assertEqual(html.count('<sup class="fn">323-1</sup>'), 3)

    def test_definition_without_a_call_still_prints_once(self):
        html = self.render(NOTE_DEF)
        self.assertEqual(html.count('class="note"'), 1)
        self.assertNotIn('[^', html)

    def test_call_inside_emphasis_and_after_punctuation(self):
        html = self.render('*[^13-1]inside* after.[^13-1]\n\n[^13-1]: Note body.')
        self.assertIn('<sup class="fn">13-1</sup>', html)
        self.assertNotIn('[^13-1]', html)

    def test_malformed_markers_stay_literal_text(self):
        for text in ('[^]', '[^ spaced]', '[^ key]: a spaced key is not a key', '[^key', '[^^12]'):
            with self.subTest(text=text):
                html = self.render(text)
                self.assertNotIn('class="note"', html)
                self.assertIn(text.lstrip('[')[:6], html)

    def test_note_keys_are_safe_labels_not_html(self):
        html = self.render('[^<b>x</b>] and [^ok]: fine')
        self.assertNotIn('<b>', html)
        self.assertIn('<sup class="fn">ok</sup>', html)

    def test_note_and_table_keep_their_source_order(self):
        html = self.render(NOTE_DEF + '\n\n' + TABLE + '\n\nAfter' + NOTE_CALL)
        self.assertLess(html.index('<p class="note">'), html.index('<table class="tbl">'))
        self.assertLess(html.index('<table class="tbl">'), html.index('After'))

    def test_body_that_is_only_a_definition_still_renders_a_block(self):
        blocks = parse_body(NOTE_DEF)
        self.assertEqual([block.kind for block in blocks], ['note'])
        self.assertEqual(blocks[0].ref, '323-1')


if __name__ == '__main__':
    unittest.main()
