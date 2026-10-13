"""Profile-driven pairwise sentence overlap; never proof of independence."""
import re
from itertools import combinations
from typing import Any, List

from ..findings import Finding
from . import Check, Context, finding, gate_status, house_sections


def sentences(text: str, min_sentence_chars: int = 40) -> List[str]:
    """Split as the established Mouseia gate, retaining repeated occurrences."""
    return [s.strip() for s in re.split(r"(?<=[.!?;:])\s+|\n", text)
            if len(s.strip()) >= min_sentence_chars]


def enabled(profile: Any) -> bool:
    """A configured threshold applies to the declared house-register pairs."""
    return profile.checks.copy_ratio is not None


def _comparisons(ctx: Context) -> list:
    return [(left, right, list(zip(ls.units, rs.units)))
            for (left, ls), (right, rs) in combinations(house_sections(ctx), 2)]


def run(ctx: Context) -> List[Finding]:
    """Compare later-register occurrences with an earlier-register sentence set."""
    result = []
    checks = ctx.profile.checks
    for left, right, pairs in _comparisons(ctx):
        for source, target in pairs:
            reference = set(sentences(source.text, checks.min_sentence_chars))
            compared = sentences(target.text, checks.min_sentence_chars)
            if len(compared) < checks.min_sentences:
                continue
            same = sum(sentence in reference for sentence in compared)
            ratio = same / len(compared)
            if ratio <= checks.copy_ratio:
                continue
            mouseia_pair = (left.id, right.id) == ('musean', 'plain')
            message = (f'{same}/{len(compared)} Plain sentences identical to Musean ({ratio:.0%})'
                       if mouseia_pair else
                       f'{same}/{len(compared)} {right.label} sentences identical to {left.label} ({ratio:.0%})')
            result.append(finding(ctx, 'REG-PLAIN-COPY' if mouseia_pair else 'REG-3', 'REG-3', message,
                                  unit=source.title, register=right.id, line=target.line,
                                  evidence={'same': same, 'total': len(compared), 'ratio': ratio,
                                            'threshold': checks.copy_ratio, 'eligible_sentences': len(compared),
                                            'compared_register': right.id, 'reference_register': left.id}))
    return result


def statuses(ctx: Context, findings: List[Finding]) -> List[dict]:
    """Keep disabled thresholds and insufficient evidence visibly distinct."""
    if not enabled(ctx.profile):
        return [gate_status('register', 'disabled', detail='copy_ratio is null')]
    comparisons = _comparisons(ctx)
    registers = [r.id for r, _ in house_sections(ctx)]
    applicable = any(len(sentences(target.text, ctx.profile.checks.min_sentence_chars)) >=
                     ctx.profile.checks.min_sentences
                     for _, _, pairs in comparisons for _, target in pairs)
    if not applicable:
        return [gate_status('register', 'inapplicable', registers,
                            'no register pair has min_sentences eligible comparison sentences')]
    result = [gate_status('register', 'failed' if findings else 'ran', registers)]
    for left, right, pairs in comparisons:
        for source, target in pairs:
            if len(sentences(target.text, ctx.profile.checks.min_sentence_chars)) < ctx.profile.checks.min_sentences:
                result.append(gate_status('register', 'inapplicable', [left.id, right.id],
                                          f'{source.title}: fewer than min_sentences eligible sentences'))
    return result


CHECK = Check('register', enabled, run, statuses)
