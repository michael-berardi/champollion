"""Synthetic emphasis fixtures; no historical passages or semantic-review claims."""
import unittest
from dataclasses import fields

from champollion.export.refs import parse_body
from champollion.export.typeset import Options, render_blocks


class ExportEmphasisTests(unittest.TestCase):
    def render(self, text, enabled=True, lang='de'):
        return render_blocks(parse_body(text), lang, Options(inline_emphasis=enabled))

    def test_opt_in_semantic_emphasis_keeps_reference_and_verse(self):
        html = self.render('[1] A *word* and **term**.\nA second *line*.')
        self.assertIn('<em>word</em>', html)
        self.assertIn('<strong>term</strong>', html)
        self.assertIn('<em>line</em>', html)
        self.assertIn('<span class="ref">1</span>', html)
        self.assertEqual(html.count('class="ln'), 2)

    def test_default_output_stays_literal_and_identical_to_disabled(self):
        blocks = parse_body('[1] A *word* and **term**.')
        old = render_blocks(blocks, 'de', Options())
        self.assertIn('A *word* and **term**.', old)
        self.assertEqual(old, render_blocks(blocks, 'de', Options(inline_emphasis=False)))

    def test_text_is_escaped_before_fixed_semantic_tags_are_added(self):
        html = self.render('*<img src=x onerror=alert(1)>* & **<script>**')
        self.assertIn('<em>&lt;img src=x onerror=alert(1)&gt;</em>', html)
        self.assertIn('<strong>&lt;script&gt;</strong>', html)
        self.assertNotIn('<img ', html)
        self.assertNotIn('<script>', html)
        self.assertIn('&amp;', html)

    def test_malformed_stars_remain_literal(self):
        for text in ('a * b', '* spaced *', 'unclosed *word', '***nested***', '**unclosed*', '**'):
            with self.subTest(text=text):
                html = self.render(text)
                self.assertIn(text, html)
                self.assertNotIn('<em>', html)
                self.assertNotIn('<strong>', html)

    def test_emphasis_does_not_cross_lines_or_consume_footnote_markers(self):
        html = self.render('[2] *Two\nlines* and a *word*.[11]')
        self.assertNotIn('<em>Two', html)
        self.assertIn('<em>word</em>', html)
        self.assertIn('<sup class="fn">11</sup>', html)

    def test_punctuation_and_unicode(self):
        html = self.render('*I*—*two words*, **αὐτός**.')
        self.assertIn('<em>I</em>—<em>two words</em>, <strong>αὐτός</strong>.', html)

    def test_opt_in_does_not_mutate_the_book_model(self):
        blocks = parse_body('[1] A *word*.')
        before = blocks[0].lines[0].plain()
        render_blocks(blocks, 'de', Options(inline_emphasis=True))
        self.assertEqual(blocks[0].lines[0].plain(), before)

    def test_new_option_is_appended_without_reordering_positional_arguments(self):
        self.assertEqual([field.name for field in fields(Options)][-5:],
                         ['toc_pages', 'folio_offset', 'folio_pages', 'markers', 'inline_emphasis'])

    def test_no_effect_without_markup(self):
        blocks = parse_body('[1] Ordinary text with a quotation: “hello”.')
        self.assertEqual(render_blocks(blocks, 'en', Options()),
                         render_blocks(blocks, 'en', Options(inline_emphasis=True)))


if __name__ == '__main__':
    unittest.main()
