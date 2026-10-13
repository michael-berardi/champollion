"""Normalize British spellings to American in Musean and Plain editions only.

Originals, historical and reference editions keep their own spelling
(docs/translation-guidelines.md §5). Usage: python3 scripts/americanize.py [--check] corpus/*.md
"""
import re, sys

STEMS = {  # British stem -> American stem (matched at word start, suffixes kept)
    'armour': 'armor', 'valour': 'valor', 'honour': 'honor', 'dishonour': 'dishonor', 'harbour': 'harbor',
    'colour': 'color', 'favour': 'favor', 'labour': 'labor', 'neighbour': 'neighbor', 'vapour': 'vapor',
    'humour': 'humor', 'clamour': 'clamor', 'endeavour': 'endeavor', 'behaviour': 'behavior', 'rumour': 'rumor',
    'splendour': 'splendor', 'vigour': 'vigor', 'rigour': 'rigor', 'ardour': 'ardor', 'odour': 'odor',
    'savour': 'savor', 'succour': 'succor', 'tumour': 'tumor', 'candour': 'candor', 'parlour': 'parlor',
    'saviour': 'savior', 'fervour': 'fervor', 'rancour': 'rancor', 'glamour': 'glamor',
    'plough': 'plow', 'mould': 'mold', 'waggon': 'wagon', 'grey': 'gray',
}
WORDS = {
    'centre': 'center', 'centres': 'centers', 'centred': 'centered', 'theatre': 'theater', 'theatres': 'theaters',
    'metre': 'meter', 'metres': 'meters', 'fibre': 'fiber', 'fibres': 'fibers', 'sombre': 'somber', 'spectre': 'specter',
    'meagre': 'meager', 'sabre': 'saber', 'sabres': 'sabers', 'lustre': 'luster', 'calibre': 'caliber',
    'defence': 'defense', 'defences': 'defenses', 'offence': 'offense', 'offences': 'offenses', 'pretence': 'pretense',
    'pretences': 'pretenses', 'licence': 'license', 'licences': 'licenses', 'judgement': 'judgment', 'judgements': 'judgments',
    'despatch': 'dispatch', 'despatched': 'dispatched', 'practise': 'practice', 'practised': 'practiced', 'practising': 'practicing',
    'fulfil': 'fulfill', 'fulfils': 'fulfills', 'fulfilment': 'fulfillment', 'enrol': 'enroll', 'enrolment': 'enrollment',
    'marvellous': 'marvelous', 'counsellor': 'counselor', 'counsellors': 'counselors', 'counselled': 'counseled', 'counselling': 'counseling',
    'travelled': 'traveled', 'travelling': 'traveling', 'traveller': 'traveler', 'travellers': 'travelers',
    'quarrelled': 'quarreled', 'quarrelling': 'quarreling', 'cancelled': 'canceled', 'levelled': 'leveled', 'labelled': 'labeled',
    'signalled': 'signaled', 'modelled': 'modeled', 'fuelled': 'fueled', 'jewelled': 'jeweled', 'jewellery': 'jewelry',
    'marshalled': 'marshaled', 'revelled': 'reveled', 'reveller': 'reveler', 'revellers': 'revelers', 'dishevelled': 'disheveled',
    'woollen': 'woolen', 'storeys': 'stories', 'amongst': 'among', 'whilst': 'while', 'kerb': 'curb',
    'manoeuvre': 'maneuver', 'manoeuvres': 'maneuvers', 'sceptre': 'scepter', 'sceptred': 'sceptered', 'sepulchre': 'sepulcher',
    'dulness': 'dullness', 'fulness': 'fullness', 'wilfully': 'willfully', 'wilful': 'willful', 'skilful': 'skillful',
    'skilfully': 'skillfully', 'instalment': 'installment', 'programme': 'program', 'ageing': 'aging', 'mediaeval': 'medieval',
}
ISE = ['organis', 'realis', 'recognis', 'harmonis', 'civilis', 'apologis', 'criticis', 'sympathis', 'symbolis',
       'characteris', 'authoris', 'colonis', 'idealis', 'baptis', 'memoris', 'stabilis', 'utilis', 'agonis', 'tantalis',
       'scandalis', 'moralis', 'immortalis', 'personalis', 'patronis', 'terroris', 'tyrannis', 'fertilis', 'neutralis',
       'jeopardis', 'epitomis', 'finalis', 'formalis', 'legalis', 'mobilis', 'penalis', 'visualis', 'summaris', 'emphasis']
ISE_RE = re.compile(r'\b(' + '|'.join(ISE) + r')(e|es|ed|ing|ation|ations|er|ers)\b', re.I)

def keep_case(src, dst):
    if src.isupper(): return dst.upper()
    if src[0].isupper(): return dst[0].upper() + dst[1:]
    return dst

STEM_RE = re.compile(r'\b(' + '|'.join(sorted(STEMS, key=len, reverse=True)) + r')([a-z]*)\b', re.I)
WORD_RE = re.compile(r'\b(' + '|'.join(WORDS) + r')\b', re.I)
STEM_SKIP = {'greyhound', 'moulin', 'ploughman'}  # none currently; placeholder for proper names

def americanize(text):
    n = 0
    def stem(m):
        nonlocal n
        word = m.group(0)
        if word.lower() in STEM_SKIP: return word
        n += 1
        return keep_case(m.group(1), STEMS[m.group(1).lower()]) + m.group(2)
    def word(m):
        nonlocal n; n += 1
        return keep_case(m.group(1), WORDS[m.group(1).lower()])
    def ise(m):
        nonlocal n
        if m.group(1).lower() == 'emphasis': return m.group(0)
        n += 1
        suf = m.group(2); z = 'z' if m.group(1)[-1].islower() else 'Z'
        return m.group(1)[:-1] + z + suf
    text = STEM_RE.sub(stem, text)
    text = WORD_RE.sub(word, text)
    text = ISE_RE.sub(ise, text)
    return text, n
