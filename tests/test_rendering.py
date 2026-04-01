import unittest
from pathlib import Path

from obsidian_to_anki.html_render import markdownish_to_html, render_inline_text
from obsidian_to_anki.models import NoteCard
from obsidian_to_anki.preview_render import preview_sections_for_card


class RenderingTests(unittest.TestCase):
    def test_render_inline_text_does_not_double_escape_code_spans(self) -> None:
        rendered = render_inline_text("Use `a < b` here")
        self.assertEqual(rendered, "Use <code>a &lt; b</code> here")

    def test_markdownish_to_html_formats_dictionary_style_entries(self) -> None:
        rendered = markdownish_to_html(
            "noun\nan informal private conversation or discussion\n- a meeting or conference of members of a particular group"
        )

        self.assertIn('<div class="dictionary-entry">', rendered)
        self.assertIn('<div class="pos">noun</div>', rendered)
        self.assertIn('<div class="gloss">an informal private conversation or discussion</div>', rendered)
        self.assertIn("<ul><li>a meeting or conference of members of a particular group</li></ul>", rendered)

    def test_markdownish_to_html_supports_part_of_speech_qualifiers(self) -> None:
        rendered = markdownish_to_html("noun (ARCHAIC)\nan old-fashioned meaning")

        self.assertIn('<div class="dictionary-entry">', rendered)
        self.assertIn('<div class="pos">noun (ARCHAIC)</div>', rendered)
        self.assertIn('<div class="gloss">an old-fashioned meaning</div>', rendered)

    def test_markdownish_to_html_supports_combining_form_labels(self) -> None:
        rendered = markdownish_to_html("combining form\nused in word formation")

        self.assertIn('<div class="dictionary-entry">', rendered)
        self.assertIn('<div class="pos">combining form</div>', rendered)
        self.assertIn('<div class="gloss">used in word formation</div>', rendered)

    def test_markdownish_to_html_supports_broader_oxford_labels(self) -> None:
        labels = [
            "proper noun",
            "mass noun",
            "auxiliary verb",
            "exclamation",
            "transitive verb",
            "abbreviation",
            "proper noun (trademark)",
        ]

        for label in labels:
            with self.subTest(label=label):
                rendered = markdownish_to_html(f"{label}\nexample meaning")
                self.assertIn('<div class="dictionary-entry">', rendered)
                self.assertIn(f'<div class="pos">{label}</div>', rendered)
                self.assertIn('<div class="gloss">example meaning</div>', rendered)

    def test_markdownish_to_html_splits_multiple_dictionary_entries_without_blank_lines(self) -> None:
        rendered = markdownish_to_html("noun\nfirst gloss\n- bullet one\nverb\nsecond gloss")

        self.assertEqual(rendered.count('class="dictionary-entry"'), 2)
        self.assertIn('<div class="pos">noun</div>', rendered)
        self.assertIn('<div class="pos">verb</div>', rendered)
        self.assertIn('<div class="gloss">second gloss</div>', rendered)
        self.assertNotIn('<div class="gloss">verb<br>second gloss</div>', rendered)

    def test_preview_sections_keep_plain_text_angle_brackets(self) -> None:
        card = NoteCard(
            front="Example",
            back="Use a < b > c in math",
            tags=[],
            source_path=Path("/tmp/example.md"),
        )

        sections = preview_sections_for_card(card, html_output=False)

        self.assertEqual(sections[1], ("Back:", "Use a < b > c in math"))

    def test_preview_sections_convert_html_only_when_requested(self) -> None:
        card = NoteCard(
            front="Example",
            back="<div>Alpha<br>Beta</div>",
            tags=[],
            source_path=Path("/tmp/example.md"),
        )

        sections = preview_sections_for_card(card, html_output=True)

        self.assertEqual(sections[1], ("Back:", "Alpha\nBeta"))

    def test_preview_sections_show_dictionary_entries_readably(self) -> None:
        card = NoteCard(
            front="confab",
            back=(
                '<div class="dictionary-entry"><div class="pos">noun</div>'
                '<div class="gloss">an informal private conversation or discussion</div>'
                "<ul><li>a meeting or conference of members of a particular group</li></ul></div>"
            ),
            tags=[],
            source_path=Path("/tmp/confab.md"),
        )

        sections = preview_sections_for_card(card, html_output=True)

        self.assertIn("noun", sections[1][1])
        self.assertIn("an informal private conversation or discussion", sections[1][1])
        self.assertIn("• a meeting or conference of members of a particular group", sections[1][1])
