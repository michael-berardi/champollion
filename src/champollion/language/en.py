"""Pure English policies ported from Mouseia's three maintenance scripts.

These functions do not select registers, mutate work documents, or infer a
language. Callers apply them only under the declared profile policy.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Optional, Union

from ..findings import ChampollionError


ARCHAIC_ALL = re.compile(r"\b(thee|thou|thy|thine|thyself|hast|hath|dost|doth|shalt|wouldst|couldst|shouldst|canst|"
                         r"mayest|art thou|'tis|'twas|whence|whither|hither|thither|wherefore|wherein|whereof|verily|"
                         r"forsooth|perchance|mayhap|methinks|unto|yonder|betwixt|whosoever|whomsoever|ere|nay|"
                         r"is wont|was wont|were wont|haply|must needs|straightway|forthwith|well-nigh|sore afraid)\b", re.I)

ARCHAIC_PLAIN = re.compile(r"\b(slay|slays|slew|slain|smite|smote|bade|behold|beheld|lo|oft|"
                           r"hitherto|henceforth|albeit|naught|aught|thence)\b", re.I)

OCR_MARKER = re.compile(r'\[OCR unclear', re.I)

DEBRIS = re.compile(r'[\^|«»{}~\\]|\*\*|__|&(?:lt|gt|amp|nbsp|quot|#\d+);')

DOUBLED = re.compile(r"\b([A-Za-z][a-z]+)\s+\1\b")

DOUBLED_OK = frozenset(['again',
 'ah',
 'alas',
 'all',
 'ambition',
 'away',
 'back',
 'blessed',
 'burn',
 'by',
 'cao',
 'come',
 'cry',
 'deep',
 'do',
 'down',
 'ever',
 'far',
 'fast',
 'go',
 'ha',
 'had',
 'happens',
 'hear',
 'here',
 'high',
 'holy',
 'hope',
 'hush',
 'imitate',
 'in',
 'is',
 'it',
 'kill',
 'listen',
 'little',
 'long',
 'look',
 'many',
 'more',
 'no',
 'now',
 'o',
 'oh',
 'on',
 'one',
 'out',
 'quick',
 'round',
 'see',
 'slowly',
 'so',
 'soon',
 'strike',
 'that',
 'there',
 'two',
 'up',
 'very',
 'well',
 'woe',
 'yan',
 'yes'])

ELLIPSIS = re.compile(r'(?<!\.)\.\.(?!\.)|\(\.\.\)')

STEMS = MappingProxyType({'armour': 'armor',
 'valour': 'valor',
 'honour': 'honor',
 'dishonour': 'dishonor',
 'harbour': 'harbor',
 'colour': 'color',
 'favour': 'favor',
 'labour': 'labor',
 'neighbour': 'neighbor',
 'vapour': 'vapor',
 'humour': 'humor',
 'clamour': 'clamor',
 'endeavour': 'endeavor',
 'behaviour': 'behavior',
 'rumour': 'rumor',
 'splendour': 'splendor',
 'vigour': 'vigor',
 'rigour': 'rigor',
 'ardour': 'ardor',
 'odour': 'odor',
 'savour': 'savor',
 'succour': 'succor',
 'tumour': 'tumor',
 'candour': 'candor',
 'parlour': 'parlor',
 'saviour': 'savior',
 'fervour': 'fervor',
 'rancour': 'rancor',
 'glamour': 'glamor',
 'plough': 'plow',
 'mould': 'mold',
 'waggon': 'wagon',
 'grey': 'gray'})

WORDS = MappingProxyType({'centre': 'center',
 'centres': 'centers',
 'centred': 'centered',
 'theatre': 'theater',
 'theatres': 'theaters',
 'metre': 'meter',
 'metres': 'meters',
 'fibre': 'fiber',
 'fibres': 'fibers',
 'sombre': 'somber',
 'spectre': 'specter',
 'meagre': 'meager',
 'sabre': 'saber',
 'sabres': 'sabers',
 'lustre': 'luster',
 'calibre': 'caliber',
 'defence': 'defense',
 'defences': 'defenses',
 'offence': 'offense',
 'offences': 'offenses',
 'pretence': 'pretense',
 'pretences': 'pretenses',
 'licence': 'license',
 'licences': 'licenses',
 'judgement': 'judgment',
 'judgements': 'judgments',
 'despatch': 'dispatch',
 'despatched': 'dispatched',
 'practise': 'practice',
 'practised': 'practiced',
 'practising': 'practicing',
 'fulfil': 'fulfill',
 'fulfils': 'fulfills',
 'fulfilment': 'fulfillment',
 'enrol': 'enroll',
 'enrolment': 'enrollment',
 'marvellous': 'marvelous',
 'counsellor': 'counselor',
 'counsellors': 'counselors',
 'counselled': 'counseled',
 'counselling': 'counseling',
 'travelled': 'traveled',
 'travelling': 'traveling',
 'traveller': 'traveler',
 'travellers': 'travelers',
 'quarrelled': 'quarreled',
 'quarrelling': 'quarreling',
 'cancelled': 'canceled',
 'levelled': 'leveled',
 'labelled': 'labeled',
 'signalled': 'signaled',
 'modelled': 'modeled',
 'fuelled': 'fueled',
 'jewelled': 'jeweled',
 'jewellery': 'jewelry',
 'marshalled': 'marshaled',
 'revelled': 'reveled',
 'reveller': 'reveler',
 'revellers': 'revelers',
 'dishevelled': 'disheveled',
 'woollen': 'woolen',
 'storeys': 'stories',
 'amongst': 'among',
 'whilst': 'while',
 'kerb': 'curb',
 'manoeuvre': 'maneuver',
 'manoeuvres': 'maneuvers',
 'sceptre': 'scepter',
 'sceptred': 'sceptered',
 'sepulchre': 'sepulcher',
 'dulness': 'dullness',
 'fulness': 'fullness',
 'wilfully': 'willfully',
 'wilful': 'willful',
 'skilful': 'skillful',
 'skilfully': 'skillfully',
 'instalment': 'installment',
 'programme': 'program',
 'ageing': 'aging',
 'mediaeval': 'medieval'})

ISE = ('organis', 'realis', 'recognis', 'harmonis', 'civilis', 'apologis', 'criticis', 'sympathis', 'symbolis', 'characteris', 'authoris', 'colonis', 'idealis', 'baptis', 'memoris', 'stabilis', 'utilis', 'agonis', 'tantalis', 'scandalis', 'moralis', 'immortalis', 'personalis', 'patronis', 'terroris', 'tyrannis', 'fertilis', 'neutralis', 'jeopardis', 'epitomis', 'finalis', 'formalis', 'legalis', 'mobilis', 'penalis', 'visualis', 'summaris', 'emphasis')

STEM_SKIP = frozenset(['greyhound', 'moulin', 'ploughman'])

ISE_RE = re.compile(r'\b(' + '|'.join(ISE) + r')(e|es|ed|ing|ation|ations|er|ers)\b', re.I)
STEM_RE = re.compile(r'\b(' + '|'.join(sorted(STEMS, key=len, reverse=True)) + r')([a-z]*)\b', re.I)
WORD_RE = re.compile(r'\b(' + '|'.join(WORDS) + r')\b', re.I)
_SENTENCE = re.compile(r'(?<=[.!?;:])\s+|\n')
_COMMENT = re.compile(r'<!--[\s\S]*?-->')


def keep_case(src: str, dst: str) -> str:
    """Apply the legacy all-uppercase or initial-capital replacement policy."""
    if src.isupper():
        return dst.upper()
    if src[0].isupper():
        return dst[0].upper() + dst[1:]
    return dst


def americanize(text: str) -> tuple[str, int]:
    """Return the legacy spelling substitutions and the exact linter count."""
    count = 0

    def stem(match: re.Match) -> str:
        nonlocal count
        word = match.group(0)
        if word.lower() in STEM_SKIP:
            return word
        count += 1
        return keep_case(match.group(1), STEMS[match.group(1).lower()]) + match.group(2)

    def word(match: re.Match) -> str:
        nonlocal count
        count += 1
        return keep_case(match.group(1), WORDS[match.group(1).lower()])

    def ise(match: re.Match) -> str:
        nonlocal count
        if match.group(1).lower() == 'emphasis':
            return match.group(0)
        count += 1
        suffix = match.group(2)
        letter = 'z' if match.group(1)[-1].islower() else 'Z'
        return match.group(1)[:-1] + letter + suffix

    text = STEM_RE.sub(stem, text)
    text = WORD_RE.sub(word, text)
    return ISE_RE.sub(ise, text), count


def sentences(text: str, min_sentence_chars: int = 40) -> list[str]:
    """Split exactly as Mouseia, keeping eligible sentences with repetitions."""
    if type(min_sentence_chars) is not int or min_sentence_chars < 1:
        raise ChampollionError('min_sentence_chars: expected a positive integer', 'REG-PLAIN-COPY')
    return [s.strip() for s in _SENTENCE.split(text) if len(s.strip()) >= min_sentence_chars]


def eligible_source(text: str, min_source_chars: int = 1500) -> bool:
    """Test the source-length eligibility of already parsed unit text."""
    if type(min_source_chars) is not int or min_source_chars < 1:
        raise ChampollionError('min_source_chars: expected a positive integer', 'VER-SHORT-UNIT')
    return len(text.strip()) >= min_source_chars


def eligible_sentences(text: str, min_sentences: int = 8,
                       min_sentence_chars: int = 40) -> bool:
    """Test the copy gate's minimum eligible-sentence denominator."""
    if type(min_sentences) is not int or min_sentences < 1:
        raise ChampollionError('min_sentences: expected a positive integer', 'REG-PLAIN-COPY')
    return len(sentences(text, min_sentence_chars)) >= min_sentences


@dataclass(frozen=True)
class NameTable(Mapping):
    """An immutable, compiled project name table with a two-argument normalizer."""

    tables: Mapping
    patterns: Mapping

    def __getitem__(self, slug: str) -> Mapping:
        return self.tables[slug]

    def __iter__(self) -> Iterator[str]:
        return iter(self.tables)

    def __len__(self) -> int:
        return len(self.tables)

    def normalize(self, slug: str, text: str) -> tuple[str, int]:
        """Replace case-sensitive whole-name variants, counting every match."""
        table = self.tables.get(slug)
        if not table:
            return text, 0
        return self.patterns[slug].subn(lambda match: table[match.group(1)], text)


def _compile_names(obj: Any, path: str) -> NameTable:
    if type(obj) is not dict:
        raise ChampollionError(f'{path}: name table: expected an object', 'REG-NAME-VARIANT')
    tables, patterns = {}, {}
    for slug, table in obj.items():
        if slug == '_comment':
            if type(table) is not str:
                raise ChampollionError(f'{path}: _comment: expected a string', 'REG-NAME-VARIANT')
            continue
        if type(slug) is not str or not slug.strip() or type(table) is not dict:
            raise ChampollionError(f'{path}: name table {slug!r}: expected a variant object', 'REG-NAME-VARIANT')
        for variant, house in table.items():
            if type(variant) is not str or not variant.strip() or type(house) is not str or not house.strip():
                raise ChampollionError(f'{path}: {slug}.{variant}: expected nonempty variant and house strings', 'REG-NAME-VARIANT')
        tables[slug] = MappingProxyType(dict(table))
        if table:
            patterns[slug] = re.compile(r'\b(' + '|'.join(map(re.escape, table)) + r')\b')
    return NameTable(MappingProxyType(tables), MappingProxyType(patterns))


def load_name_table(path: Union[str, Path]) -> NameTable:
    """Read and validate a local UTF-8 name table, compiling names once."""
    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ChampollionError(f'{path}: {key}: duplicate name-table key', 'REG-NAME-VARIANT')
            result[key] = value
        return result

    def constant(value: str) -> None:
        raise ChampollionError(f'{path}: name table: nonfinite number {value}', 'REG-NAME-VARIANT')

    try:
        text = Path(path).read_bytes().decode('utf-8')
        obj = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise ChampollionError(f'{path}: cannot load name table: {exc}', 'REG-NAME-VARIANT') from exc
    return _compile_names(obj, str(path))


def normalize(slug: str, text: str, table: Mapping) -> tuple[str, int]:
    """Apply an explicit project table with Mouseia's substitution semantics."""
    if not isinstance(table, Mapping):
        raise ChampollionError('name table: expected a mapping', 'REG-NAME-VARIANT')
    compiled = table if isinstance(table, NameTable) else _compile_names(dict(table), '<name table>')
    return compiled.normalize(slug, text)


SUPPORTED_NOTATIONS = ('leading-number', 'decimal', 'bracket-decimal', 'parenthesis-decimal',
                       'bare-number', 'word-number', 'double-danda', 'folio', 'bekker')
_MARKERS = MappingProxyType({
    'leading-number': re.compile(r'^[ \t]*\d+\.(?!\d)', re.M),
    'decimal': re.compile(r'^[ \t]*\d+(?:\.\d+)+(?:\.(?!\d))?(?=\s|$)', re.M),
    'bracket-decimal': re.compile(r'\[\d+(?:\.\d+)+\]'),
    'parenthesis-decimal': re.compile(r'\(\d+(?:\.\d+)+\)'),
    'bare-number': re.compile(r'^[ \t]*\d+(?=[ \t]+|$)', re.M),
    'word-number': re.compile(r'\[[^\W\d_]+[ \t]+\d+\]'),
    'double-danda': re.compile(r'॥[^॥\n]+॥'),
    'folio': re.compile(r'\[\d+[a-zA-Z]\]'),
    'bekker': re.compile(r'\[Bekker[ \t]+\d+[ab][ \t]+line[ \t]+\d+\]'),
})


def notation_id(name: str) -> str:
    """Resolve a declared notation's literal example or canonical identifier."""
    aliases = {'N.': 'leading-number', 'N.N': 'decimal', '[N.N]': 'bracket-decimal',
               '(N.N)': 'parenthesis-decimal', 'NNN': 'bare-number',
               '[<word> N]': 'word-number', '॥…॥': 'double-danda',
               '[17b]': 'folio', '[Bekker 1447a line 8]': 'bekker'}
    return aliases.get(name, name.lower())


def select_notations(notation: Optional[Union[str, list[str]]] = None) -> tuple:
    """Return selected identifiers and explicitly named unsupported notations."""
    if notation is None or notation == 'auto':
        return SUPPORTED_NOTATIONS, []
    names = [s.strip() for s in notation.split(',')] if isinstance(notation, str) else notation
    if not isinstance(names, (list, tuple)) or not all(isinstance(n, str) for n in names):
        return (), [repr(notation)]
    ids = tuple(notation_id(name) for name in names)
    return ids, [name for name, ident in zip(names, ids) if ident not in SUPPORTED_NOTATIONS]


def extract_reference_markers(text: str, notation: Optional[Union[str, list[str]]] = None) -> list[str]:
    """Extract ordered marker lexemes, refusing unsupported declared notations."""
    selected, unsupported = select_notations(notation)
    if unsupported:
        raise ChampollionError('unsupported numbering notation: ' + ', '.join(unsupported), 'SEG-NUMBERING')
    hits = []
    clean = _COMMENT.sub('', text)
    for name in selected:
        for match in _MARKERS[name].finditer(clean):
            hits.append((match.start(), match.end(), match.group(0).strip()))
    hits.sort(key=lambda hit: (hit[0], -hit[1]))
    result, last_end = [], -1
    for start, end, marker in hits:
        if start >= last_end:
            result.append(marker)
            last_end = end
    return result


extract_markers = extract_reference_markers
