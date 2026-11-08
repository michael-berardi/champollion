"""Champollion ships no built-in model, provider or person choice.

Champollion is a neutral tool. What it ships names no model, provider or
fallback choice and no person's or client's name: those belong to the
operator. This test keeps it that way, modelled on Carl's neutrality test.

Not scanned, by design:

* ``LICENSE`` and ``LICENSE-docs``: legal attribution.
* The ``authors`` field of ``pyproject.toml``: package-metadata attribution.
  The rest of ``pyproject.toml`` (version, URLs, description) is scanned.
* The neutrality test itself: it contains examples of the patterns.

Documented technical identities that stay named on purpose:

* ``Mouseia`` and ``Musean`` are an external legacy-corpus and format
  identity. The compatibility layer (``src/champollion/compat/mouseia.py``),
  its adapter (``src/champollion/adapters/mouseia.py``), the ``mouseia``
  profile key and its documented history must name them for
  interoperability; renaming would break users' existing profiles.
* ``Champollion`` is the protocol's own name.

A bare word such as ``fallback`` is not a fallback chain by itself: it occurs
in generic CSS (``fallback:decimal``) and licence wording. A chain cannot be
expressed without naming a model id or a provider route, which the model
pattern catches; an ordered declaration in brackets or braces is caught by
``FALLBACK_CHAIN``.
"""
import os
import re
import tempfile
from pathlib import Path
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHIPPED_DIRS = ["src", "docs", "profiles", "scripts", "examples"]
SHIPPED_FILES = [
    "README.md",
    "SPEC.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "THIRD-PARTY.md",
    "MANIFEST.in",
    "CITATION.cff",
    "pyproject.toml",
    "Makefile",
    # Legal attribution: listed as candidates, then excluded below.
    "LICENSE",
    "LICENSE-docs",
]
# Documented allowlist: legal attribution, excluded from the scan.
LEGAL_ATTRIBUTION_FILES = {"LICENSE", "LICENSE-docs"}
# Documented allowlist: package-metadata attribution lines, excluded from the scan.
METADATA_ATTRIBUTION_PREFIXES = ("authors =",)

# Concrete model ids and provider routes that only an operator should choose.
# Agent names in compatibility lists (Claude Code, Codex, Gemini CLI) are not
# model choices and are not matched here.
MODEL_CHOICE = re.compile(
    r"\b(?:gpt-\d[\w.-]*|o[134]-(?:mini|pro|preview)\b"
    r"|claude-(?:opus|sonnet|haiku|fable|instant|\d)[\w.-]*"
    r"|(?:opus|sonnet|haiku|fable) ?\d(?:[.-]\d)?\b"
    r"|gemini-\d[\w.-]*|deepseek[\w.-]*|qwen-?\d[\w.-]*"
    r"|kimi-k\d[\w.-]*|glm-\d[\w.-]*|mimo-v\d[\w.-]*"
    r"|llama-?\d[\w.-]*|grok-\d[\w.-]*)"
    r"|(?<![\w./])(?:openrouter|anthropic|openai|opencode-go|x-ai|mistralai)/[\w.-]+"
    r"|:exacto\b",
    re.IGNORECASE,
)
# An ordered fallback declaration, e.g. "fallback": ["provider-a/model"].
FALLBACK_CHAIN = re.compile(r"\bfallbacks?\b\s*[\"']?\s*[:=]\s*[\[{]", re.IGNORECASE)
# Personal names and private home paths. Case-insensitive so a lowercase
# handle in a URL cannot slip through. Mouseia is deliberately absent: it is
# an external format identity, not a person.
PERSONAL = re.compile(
    r"\b(?:Mike|Michael|Berardi|Liberty ?Design)\b"
    r"|libertydesign|/Users/[a-z]",
    re.IGNORECASE,
)
# Documented exceptions: (relative file, text the line contains, why it stays).
# Empty today: neutral placeholders read as well as the original handle.
ALLOWED = ()


def load_private_terms(path=None):
    path = Path(path or os.environ.get("OSS_PRIVATE_TERMS", "~/.config/oss-audit/names.txt")).expanduser()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    terms = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    if not terms:
        return None
    patterns = [(r"\b" if term[0].isalnum() or term[0] == "_" else "")
                + re.escape(term)
                + (r"\b" if term[-1].isalnum() or term[-1] == "_" else "")
                for term in terms]
    return re.compile("|".join(patterns), re.IGNORECASE)


def walk(directory):
    for name in sorted(os.listdir(directory)):
        if name == "__pycache__":
            continue
        full = os.path.join(directory, name)
        if os.path.isdir(full):
            yield from walk(full)
        elif not name.endswith(".pyc"):
            yield full


def shipped(include_tests=False):
    """Every scanned text as (relative path, content)."""
    files = []
    for directory in SHIPPED_DIRS:
        files.extend(walk(os.path.join(ROOT, directory)))
    if include_tests:
        files.extend(walk(os.path.join(ROOT, "tests")))
    files.extend(os.path.join(ROOT, name) for name in SHIPPED_FILES)
    texts = []
    for path in files:
        relative = os.path.relpath(path, ROOT)
        if relative == "tests/test_neutrality.py" or relative in LEGAL_ATTRIBUTION_FILES:
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        if relative == "pyproject.toml":
            text = "\n".join(
                line for line in text.splitlines()
                if not line.startswith(METADATA_ATTRIBUTION_PREFIXES)
            )
        texts.append((relative, text))
    return texts


def hits(pattern, include_tests=False):
    found = []
    for file, text in shipped(include_tests):
        for number, line in enumerate(text.splitlines(), 1):
            if not pattern.search(line):
                continue
            if any(f == file and contains in line for f, contains, _ in ALLOWED):
                continue
            found.append("%s:%d: %s" % (file, number, line.strip()[:120]))
    return found


class NeutralityTests(unittest.TestCase):
    def test_private_terms_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "terms.txt"
            path.write_text("# comment\n\nzzqx-private-term\n", encoding="utf-8")
            pattern = load_private_terms(path)
            self.assertIsNotNone(pattern)
            text = Path(directory) / "sample.txt"
            text.write_text("a ZZQX-private-term here", encoding="utf-8")
            self.assertRegex(text.read_text(encoding="utf-8"), pattern)
            text.write_text("a neutral text", encoding="utf-8")
            self.assertNotRegex(text.read_text(encoding="utf-8"), pattern)
            self.assertNotRegex("azzqx-private-termz", pattern)
            self.assertIsNone(load_private_terms(Path(directory) / "missing"))

    def test_scans_the_shipped_tree_not_an_empty_set(self):
        scanned = shipped()
        files = [file for file, _ in scanned]
        for expected in (
            "src/champollion/__init__.py",
            "src/champollion/cli.py",
            "src/champollion/compat/mouseia.py",
            "profiles/generic.json",
            "profiles/mouseia.json",
            "README.md",
            "SPEC.md",
            "pyproject.toml",
            "CITATION.cff",
            "Makefile",
        ):
            self.assertIn(expected, files)
        lines = sum(len(text.splitlines()) for _, text in scanned)
        self.assertGreater(lines, 1000)
        # Legal attribution stays out of the scan; the rest of pyproject stays in.
        self.assertNotIn("LICENSE", files)
        self.assertNotIn("LICENSE-docs", files)

    def test_catches_what_it_guards_and_spares_neutral_placeholders(self):
        for sample in (
            "claude-opus-5-5",
            "gpt-5.1",
            "openrouter/deepseek/deepseek-v4",
            "Sonnet 5.5",
            "glm-4.6",
            "gemini-2.5-pro",
        ):
            self.assertRegex(sample, MODEL_CHOICE)
        for sample in (
            '"fallback": ["provider-a/model-name"]',
            "fallbacks = [{'provider': 'x'}]",
        ):
            self.assertRegex(sample, FALLBACK_CHAIN)
        for sample in (
            "https://github.com/michael-berardi/champollion",
            "Michael Berardi",
            "/Users/someone/dev",
            "Liberty Design",
        ):
            self.assertRegex(sample, PERSONAL)
        for sample in (
            "provider-a/model-name",
            "claude --profile-dir",
            "Gemini CLI",
            "OpenCode",
            "Mouseia",
            "Musean",
            "fallback:decimal",
        ):
            self.assertNotRegex(sample, MODEL_CHOICE)
        for sample in (
            "fallback:decimal",
            "fallback license",
            "fallback: auto",
        ):
            self.assertNotRegex(sample, FALLBACK_CHAIN)
        for sample in (
            "https://github.com/your-github-username/champollion",
            "your-org/champollion",
            "Alex",
            "Mouseia",
            "Musean",
            "Champollion",
        ):
            self.assertNotRegex(sample, PERSONAL)

    def test_ships_no_concrete_model_id_or_provider_preference(self):
        self.assertEqual(hits(MODEL_CHOICE), [])

    def test_ships_no_ordered_fallback_chain(self):
        self.assertEqual(hits(FALLBACK_CHAIN), [])

    def test_names_no_person_or_private_path(self):
        self.assertEqual(hits(PERSONAL, include_tests=True), [])
        private = load_private_terms()
        if private:
            self.assertEqual(hits(private, include_tests=True), [])


if __name__ == "__main__":
    unittest.main()
