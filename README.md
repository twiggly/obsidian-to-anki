# Obsidian to Anki

Convert Obsidian notes tagged with `#definition` into an Anki-importable TSV file or sync them directly to Anki.

The project supports:

- a command-line workflow
- a desktop Tkinter UI
- optional direct sync to Anki through [AnkiConnect](https://github.com/FooSoft/anki-connect)

## Install

This project only uses the Python standard library.

```bash
python3 -m pip install .
```

That installs a console script named `obsidian-to-anki`.

## Usage

### GUI

Open the desktop UI:

```bash
obsidian-to-anki
```

or:

```bash
python3 main.py
```

When direct Anki sync is enabled in the GUI:

- `Load from Anki` populates the deck and note type dropdowns from AnkiConnect
- the front and back field dropdowns refresh automatically for the selected note type
- the last-used GUI settings are restored the next time you open the app

### CLI

Export notes from a vault into a TSV file:

```bash
obsidian-to-anki --vault /path/to/vault --output /path/to/obsidian-to-anki.tsv
```

Useful options:

- `--tag`: match a tag other than `definition`
- `--html`: render the card back as simple HTML
- `--italicize-quoted-text`: italicize quoted text when `--html` is enabled
- `--skip-empty`: skip notes whose cleaned body is empty
- `--include-folder`: repeat to include one or more folders inside the vault
- `--duplicate-handling`: choose how to handle duplicate card fronts: `skip`, `suffix`, or `error`
- `--anki`: sync matching notes directly to Anki via AnkiConnect
- `--anki-deck`: choose the Anki deck for direct sync
- `--anki-note-type`: choose the Anki note type for direct sync
- `--anki-existing-notes`: choose whether existing Anki notes are `skip`ped or `update`d

Example:

```bash
obsidian-to-anki \
  --vault /path/to/vault \
  --output /path/to/obsidian-to-anki.tsv \
  --html \
  --duplicate-handling suffix \
  --italicize-quoted-text \
  --include-folder Lexicon \
  --include-folder Study
```

Direct sync without writing a TSV file:

```bash
obsidian-to-anki \
  --vault /path/to/vault \
  --anki \
  --anki-deck Lexicon \
  --anki-note-type Basic
```

You can also combine both destinations in one run by providing `--output` and `--anki` together.

When a run has duplicate-front resolutions or skipped/updated Anki notes, the app prints those details in the GUI status log or directly in the CLI output after the summary.

## Duplicate Handling

When multiple matching notes would produce the same card front, you can choose a strategy:

- `skip`: keep only the first matching note for each front
- `suffix`: keep all cards and append a folder-based suffix to duplicate fronts
- `error`: stop immediately if duplicate fronts are found

Examples with `suffix`:

- `Term` becomes `Term (Lexicon)`
- `Term` becomes `Term (Study)`

## Anki Sync

Direct sync uses [AnkiConnect](https://github.com/FooSoft/anki-connect). In both the CLI and GUI you can:

- pick a deck and note type
- map the front and back fields from the selected note type
- choose how existing notes are handled:
  - `skip`: leave existing Anki notes unchanged
  - `update`: update matching Anki notes instead of skipping them

Matching existing notes are identified by the selected note type and the configured front field value.

## Note Format

The typical note style for this project is:

- the filename becomes the card front
- the note body becomes the card back
- a trailing `#definition` tag includes the note in export

Example note file: `confab.md`

```text
noun
an informal private conversation or discussion
- a meeting or conference of members of a particular group

verb
engage in informal private conversation

#definition
```

This exports roughly as:

- Front: `confab`
- Back: the note body without the trailing tag
- Tags: `definition`

The exporter also supports:

- frontmatter tags
- HTML comments being ignored for tag detection
- markdown link fragments like `[link](#heading)` not counting as tags
- Obsidian wikilink heading fragments like `[[#heading|label]]` not counting as tags
- UTF-8 BOM-prefixed notes

## HTML Rendering

When `--html` is enabled, the exporter converts simple note formatting into lightweight HTML suitable for Anki.

Dictionary-style part-of-speech headings such as these are recognized:

- `noun`
- `noun (ARCHAIC)`
- `verb`
- `combining form`
- `proper noun`
- `mass noun`
- `auxiliary verb`

These render into HTML sections with the following classes:

- `.dictionary-entry`
- `.pos`
- `.gloss`

That means you can style Anki cards with CSS like:

```css
.back .dictionary-entry {
  margin: 0 0 0.9em 0;
  padding-left: 0.8em;
  border-left: 3px solid #b8b1a6;
}

.back .pos {
  font-size: 0.68em;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.back .gloss {
  margin: 0 0 0.28em 0;
}
```

## Project Layout

The project is split into small modules by responsibility:

- `cli.py`: command-line argument parsing and entrypoint
- `anki_sync.py`: direct AnkiConnect validation and sync
- `delivery.py`: shared export and sync orchestration
- `scanner.py`: compatibility facade for note scanning helpers
- `scan_filters.py`: vault path and folder filtering logic
- `note_parser.py`: frontmatter and tag extraction
- `scanner_engine.py`: card scanning and duplicate-front summaries
- `rendering.py`: compatibility facade for rendering helpers
- `body_cleanup.py`: note-body cleanup before export
- `html_render.py`: HTML rendering and dictionary-entry formatting
- `preview_render.py`: preview text conversion and preview widget population
- `gui.py`: GUI controller
- `gui_view.py`: Tk widget construction and picker/listbox behavior
- `gui_logic.py`: pure GUI form and message helpers
- `gui_settings.py`: GUI settings persistence
- `gui_tasks.py`: preview/export background task wiring
- `gui_preview.py`: preview dialog
- `reporting.py`: post-run duplicate and sync report writing

## Tests

Run the full test suite with:

```bash
make test
```

or:

```bash
python3 -m unittest -v
```
