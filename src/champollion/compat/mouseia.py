"""Corpus lint for Mouseia editions (docs/translation-guidelines.md).

Checks the reader-facing Musean and Plain English editions of every corpus/*.md work
for the defect classes found in the 2026-09-24 audit: scan debris, raw markup, doubled
words, archaic grammar, British spelling, Plain copied from Musean, and units whose
English is far shorter than the source.

Usage:
  python3 scripts/lint_corpus.py            # lint all works; exit 1 on any error
  python3 scripts/lint_corpus.py --verbose  # also print warnings
  python3 scripts/lint_corpus.py corpus/iliad.md

Known, tracked exceptions live in scripts/lint-baseline.json as
{"<slug>": {"<check>": ["<unit heading>", ...]}}. Remove entries as works are fixed.
"""
import json, os, re, sys
from pathlib import Path

from ._spelling import americanize

def normalize_names(slug, text, names):
    table = names.get(slug, {})
    if not table:
        return text, 0
    pattern = re.compile(r'\b(' + '|'.join(map(re.escape, table)) + r')\b')
    return pattern.subn(lambda m: table[m.group(1)], text)

SECTIONS = {'original': 'orig', 'mouseia translation': 'mus', 'curated translation': 'mus',
            'plain translation': 'plain', 'plain english translation': 'plain',
            'reference translation': 'ref', 'historical translation': 'hist'}

# Dead grammar: never in Musean or Plain.
ARCHAIC_ALL = re.compile(r"\b(thee|thou|thy|thine|thyself|hast|hath|dost|doth|shalt|wouldst|couldst|shouldst|canst|"
                         r"mayest|art thou|'tis|'twas|whence|whither|hither|thither|wherefore|wherein|whereof|verily|"
                         r"forsooth|perchance|mayhap|methinks|unto|yonder|betwixt|whosoever|whomsoever|ere|nay|"
                         r"is wont|was wont|were wont|haply|must needs|straightway|forthwith|well-nigh|sore afraid)\b", re.I)
# Literary words acceptable in Musean but not in Plain.
ARCHAIC_PLAIN = re.compile(r"\b(slay|slays|slew|slain|smite|smote|bade|behold|beheld|lo|oft|"
                           r"hitherto|henceforth|albeit|naught|aught|thence)\b", re.I)
OCR_MARKER = re.compile(r'\[OCR unclear', re.I)
DEBRIS = re.compile(r'[\^|«»{}~\\]|\*\*|__|&(?:lt|gt|amp|nbsp|quot|#\d+);')
DOUBLED = re.compile(r"\b([A-Za-z][a-z]+)\s+\1\b")
DOUBLED_OK = {'cao', 'yan', 'had', 'that', 'very', 'far', 'so', 'on', 'o', 'ah', 'woe', 'come', 'go', 'again',
              'by', 'out', 'more', 'round', 'ever', 'two', 'one', 'deep', 'do', 'yes', 'no', 'is', 'long', 'little',
              'many', 'fast', 'slowly', 'away', 'well', 'in', 'cry', 'imitate', 'happens', 'ambition', 'it', 'hope',
              'all', 'on', 'up', 'down', 'back', 'high', 'now', 'here', 'there', 'soon', 'blessed', 'holy', 'kill',
              'strike', 'burn', 'hear', 'listen', 'look', 'see', 'alas', 'oh', 'ha', 'hush', 'quick', 'on'}
ELLIPSIS = re.compile(r'(?<!\.)\.\.(?!\.)|\(\.\.\)')
# House markup the reader renders: **strong** (Kant's spaced type), footnote calls and
# definitions ([^key] / [^key]: text) and pipe tables. Only these spans are exempt from
# the raw-markup check; an unbalanced **, a stray pipe or a bare ^ is still debris.
STRONG = re.compile(r'\*\*[^*\n]+\*\*')
FOOTNOTE_TOKEN = re.compile(r'\[\^[A-Za-z0-9_-]+\]')
TABLE_LINE = re.compile(r'^\s*\|')


def rendered(line):
    """Return the line with supported house markup removed, for the debris check."""
    text = FOOTNOTE_TOKEN.sub('', STRONG.sub('', line))
    if TABLE_LINE.match(text):
        return '\x00'.join(re.split(r'(?<!\\)\|', text.strip().strip('|')))
    return text


COPY_RATIO = 0.35
# Works whose editions mark speech with straight double quotes line by line; the
# structural speech-mark check runs on these (2026-09-24 audit: unclosed speeches).
SPEECH_MARK_WORKS = {'iliad', 'odyssey'}
SHORT_UNIT = 0.5
MIN_SENT = 40


def load(path):
    raw = Path(path).read_text(encoding='utf8')
    m = re.match(r'^---\n([\s\S]*?)\n---\n([\s\S]*)$', raw)
    if not m:
        return None
    start = raw[:m.start(2)].count('\n') + 1
    secs, cur = {}, None
    for i, line in enumerate(m.group(2).split('\n')):
        h = re.match(r'^##\s+(.+)$', line)
        if h:
            cur = SECTIONS.get(h.group(1).strip().lower())
            if cur:
                secs[cur] = []
            continue
        if cur:
            secs[cur].append((start + i, line))
    works = {}
    for key, lines in secs.items():
        units, unit = [], None
        for ln, line in lines:
            h = re.match(r'^###\s+(.+)$', line)
            if h:
                unit = {'head': h.group(1).strip(), 'lines': []}
                units.append(unit)
                continue
            if unit is None:
                unit = {'head': '(whole work)', 'lines': []}
                units.append(unit)
            unit['lines'].append((ln, line))
        for u in units:
            text = '\n'.join(l for _, l in u['lines'])
            u['text'] = re.sub(r'<!--[\s\S]*?-->', '', text).strip()
        works[key] = [u for u in units if u['text'] or u['head'] != '(whole work)']
    return works


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?;:])\s+|\n', text) if len(s.strip()) >= MIN_SENT]


def lint(path, baseline, names=None):
    slug = os.path.basename(path)[:-3]
    works = load(path)
    if works is None or 'orig' not in works:
        return [], []
    base = baseline.get(slug, {})
    errors, warnings = [], []

    def report(check, unit, msg, severity='error'):
        allowed = unit in base.get(check, []) or '*' in base.get(check, [])
        (warnings if severity == 'warn' or allowed else errors).append(f'{slug} [{unit}] {check}: {msg}')

    for reg, label in (('mus', 'Musean'), ('plain', 'Plain')):
        for u in works.get(reg, []):
            for ln, line in u['lines']:
                if line.lstrip().startswith('<!--'):
                    continue
                where = f'line {ln}'
                if OCR_MARKER.search(line):
                    report('ocr-marker', u['head'], f'{label} {where}: raw [OCR unclear] marker')
                checked = rendered(line)
                d = DEBRIS.search(checked)
                if d:
                    report('debris', u['head'], f'{label} {where}: {d.group(0)!r} in “…{checked[max(0, d.start() - 30):d.end() + 30]}…”')
                for m in DOUBLED.finditer(line):
                    if m.group(1).lower() not in DOUBLED_OK:
                        report('doubled-word', u['head'], f'{label} {where}: “{m.group(0)}”')
                a = ARCHAIC_ALL.search(line)
                if a:
                    report('archaism', u['head'], f'{label} {where}: “{a.group(0)}”')
                if reg == 'plain':
                    a = ARCHAIC_PLAIN.search(line)
                    if a:
                        report('plain-archaism', u['head'], f'{where}: “{a.group(0)}”')
                if ELLIPSIS.search(line):
                    report('ellipsis', u['head'], f'{label} {where}: use a single “…”', 'warn')
            _, n = americanize(u['text'])
            if n:
                report('spelling', u['head'], f'{label}: {n} British spellings (run scripts/americanize.py)')
            _, n = normalize_names(slug, u['text'], names or {})
            if n:
                report('name-variant', u['head'], f'{label}: {n} non-house name spellings (run scripts/normalize_names.py)')

    if slug in SPEECH_MARK_WORKS:
        for reg, label in (('mus', 'Musean'), ('plain', 'Plain')):
            for u in works.get(reg, []):
                open_at = None
                for ln, line in u['lines']:
                    for i, ch in enumerate(line):
                        if ch != '"':
                            continue
                        opening = i == 0 or line[i - 1] in ' (—'
                        if opening and open_at:
                            report('speech-marks', u['head'], f'{label} line {ln}: new speech opens while the one from line {open_at} is unclosed')
                        if not opening and not open_at:
                            report('speech-marks', u['head'], f'{label} line {ln}: closing mark with no open speech')
                        open_at = ln if opening else None
                if open_at:
                    report('speech-marks', u['head'], f'{label} line {open_at}: speech never closed')

    for m, p in zip(works.get('mus', []), works.get('plain', [])):
        ms, ps = set(sentences(m['text'])), sentences(p['text'])
        if len(ps) >= 8:
            same = sum(1 for s in ps if s in ms)
            if same / len(ps) > COPY_RATIO:
                report('plain-copy', m['head'], f'{same}/{len(ps)} Plain sentences identical to Musean ({same / len(ps):.0%})')

    # A unit whose English is much shorter, relative to its source, than is usual for the
    # same work usually has omissions or a misaligned source (Lucretius I, 2026-09-24).
    triples = [(o, m, p) for o, m, p in zip(works['orig'], works.get('mus', []), works.get('plain', []))
               if len(o['text']) >= 1500]
    for reg_index, label in ((1, 'Musean'), (2, 'Plain')):
        ratios = sorted(len(t[reg_index]['text']) / len(t[0]['text']) for t in triples)
        if len(ratios) < 3:
            continue
        median = ratios[len(ratios) // 2]
        for t in triples:
            ratio = len(t[reg_index]['text']) / len(t[0]['text'])
            if ratio < SHORT_UNIT * median:
                report('short-unit', t[0]['head'], f'{label} English/source length is {ratio:.2f}, work median {median:.2f}; '
                       'check for omitted or misaligned text')
    return errors, warnings


def main(argv=None, root=None):
    if root is None:
        raise ValueError('Mouseia compatibility gate requires a project root')
    corpus = os.path.join(root, 'corpus')
    baseline_path = os.path.join(root, 'scripts', 'lint-baseline.json')
    names_path = os.path.join(root, 'scripts', 'names.json')
    argv = list(sys.argv[1:] if argv is None else argv)
    unknown = [a for a in argv if a.startswith('--') and a != '--verbose']
    if unknown:
        print('Champollion Mouseia compatibility: unknown argument ' + unknown[0], file=sys.stderr)
        return 2
    args = [a for a in argv if not a.startswith('--')]
    verbose = '--verbose' in argv
    baseline = json.loads(Path(baseline_path).read_text(encoding='utf8')) if os.path.exists(baseline_path) else {}
    names = json.loads(Path(names_path).read_text(encoding='utf8'))
    paths = args or sorted(os.path.join(corpus, f) for f in os.listdir(corpus) if f.endswith('.md') and f != 'SOURCES.md')
    all_errors, all_warnings = [], []
    for path in paths:
        e, w = lint(path, baseline, names)
        all_errors += e
        all_warnings += w
    if verbose:
        for w in all_warnings:
            print('warn  ', w)
    for e in all_errors:
        print('ERROR ', e)
    print(f'lint:corpus — {len(paths)} works, {len(all_errors)} errors, {len(all_warnings)} warnings/baselined')
    return 1 if all_errors else 0


# Use main(argv, root) from a host-project wrapper.
