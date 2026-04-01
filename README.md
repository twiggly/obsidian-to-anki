# Obsidian to Anki

Convert Obsidian notes matching one or more selected tags into an Anki-importable TSV file or sync them directly to Anki.

The project supports:

- a command-line workflow
- a desktop Tkinter UI
- optional direct sync to Anki through [AnkiConnect](https://github.com/FooSoft/anki-connect)
- duplicate handling for same-front notes
- both TSV export and direct Anki sync in the same run

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

or, using the package entrypoint directly:

```bash
python3 -m obsidian_to_anki
```

The GUI flow is:

1. choose a vault
2. optionally turn on TSV export and choose an output file
3. select one or more tags to match
4. optionally limit the scan to specific folders
5. preview the first matching cards before exporting or syncing, unless duplicate handling is set to `error` and duplicates must be resolved first

When direct Anki sync is enabled in the GUI:

- the connection indicator checks AnkiConnect automatically
- the deck and note type dropdowns populate from AnkiConnect
- existing notes can be skipped or updated
- `Install 'Term & Definition' Note Type` installs or updates the bundled `Term & Definition (Obsidian)` note type with forward and reverse cards
- `Apply Recommended Deck Settings` creates or updates a dedicated deck preset for the selected deck
- preview warns if Anki is unavailable or the recommended note type is not selected, but still opens so you can inspect cards
- the last-used GUI settings are restored the next time you open the app
- the status area keeps a compact summary by default, with expandable details

Current GUI defaults:

- `Output TSV` starts turned off
- `Flatten note links` starts turned off
- note bodies that clean down to empty content are skipped automatically

### CLI

Export notes from a vault into a TSV file:

```bash
obsidian-to-anki --vault /path/to/vault --output /path/to/obsidian-to-anki.tsv
```

Useful options:

- `--tag`: match a tag other than `definition`
- `--html`: render the card back as simple HTML
- `--italicize-quoted-text`: italicize quoted text when `--html` is enabled
- `--preserve-note-links`: keep Obsidian and Markdown note-link syntax instead of flattening links to plain text
- note bodies that clean down to empty content are skipped automatically
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
- choose how existing notes are handled:
  - `skip`: leave existing Anki notes unchanged
  - `update`: update matching Anki notes instead of skipping them

In the GUI, deck and note type choices are loaded from AnkiConnect and the app auto-selects front and back fields from the available field list. In the CLI, you can still specify the front and back fields explicitly.

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
- markdown and Obsidian note links being flattened to readable text by default in the CLI, with a GUI toggle to turn link flattening on when you want it
- note bodies that clean down to empty content being skipped automatically
- UTF-8 BOM-prefixed notes
- dot-prefixed vault folders and files like `.obsidian/`, `.trash/`, and `.Hidden.md` being ignored during scans

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

The app code now lives in the `obsidian_to_anki/` package, with:

- `obsidian_to_anki/__main__.py` for `python3 -m obsidian_to_anki`
- a small top-level `main.py` compatibility wrapper for `python3 main.py`

Key modules inside `obsidian_to_anki/`:

- `cli.py`: command-line argument parsing and entrypoint
- `anki/`: direct AnkiConnect client, catalog, existing-note lookup, and sync engine
- `anki_sync.py`: compatibility facade for the `anki/` subpackage
- `delivery.py`: shared export and sync orchestration
- `scanner.py`: compatibility facade for note scanning helpers
- `scan_filters.py`: vault path and folder filtering logic
- `note_parser.py`: frontmatter and tag extraction
- `scanner_engine.py`: card scanning and duplicate-front summaries
- `rendering.py`: compatibility facade for rendering helpers
- `body_cleanup.py`: note-body cleanup before export
- `html_render.py`: HTML rendering and dictionary-entry formatting
- `preview_render.py`: preview text conversion and preview widget population
- `gui/`: GUI controller, view, widget, task, and settings modules
- `gui_*.py`: compatibility facades for the `gui/` subpackage
- `reporting.py`: post-run duplicate and sync reporting

The test suite now lives in the `tests/` package.

## Tests

Run the full test suite with:

```bash
make test
```

or:

```bash
python3 -m unittest discover -s tests -v
```

## Branch and PR Workflow

For a lightweight GitHub workflow from this repo:

```bash
make sync-main
make branch NAME=improve-sync-copy
```

Make your changes, then open a draft PR with:

```bash
make pr
```

What these do:

- `make sync-main`: switch to `main` and fast-forward from `origin/main`
- `make branch NAME=...`: create and switch to `codex/...`
- `make pr`: run tests, push the current branch, and open a draft PR with `gh`

If you just want to see the available helper commands:

```bash
make help
```
