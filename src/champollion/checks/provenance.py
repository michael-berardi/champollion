"""Core scalar provenance completeness and SPEC field constraints."""
import datetime
from pathlib import PurePosixPath
import re
from typing import Any, List
from urllib.parse import urlsplit

from ..findings import Finding
from . import Check, Context, finding

BASE_KEYS = ("slug", "title", "author", "tradition", "language", "genre", "period",
             "source_url", "raw_snapshot", "completeness", "source_scope", "as_of",
             "certainty", "source", "status", "unknowns")
LANGUAGE_TAG = re.compile(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*\Z")


def enabled(profile: Any) -> bool:
    """Provenance is mandatory for every profile."""
    return True


def _invalid(key: str, value: str, ctx: Context) -> str:
    if key == "slug" and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        return "slug must be lowercase hyphen-separated letters and digits"
    if key == "language":
        if not LANGUAGE_TAG.fullmatch(value):
            return "language must be a BCP-47 tag"
        source = ctx.profile.source
        if source is not None and value.lower() != source["tag"].lower():
            return "language differs from the profile source language"
    if key == "source_url":
        try:
            parsed = urlsplit(value)
        except ValueError as exc:
            return "source_url is not a valid URI: " + str(exc)
        if not parsed.scheme or any(c.isspace() for c in value):
            return "source_url must be a source-identifying URI"
    if key in ("raw_snapshot", "source"):
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or urlsplit(value).scheme:
            return key + " must be a project-relative local path/reference"
    if key == "completeness" and value != "complete":
        return "completeness must be complete"
    if key == "source_scope" and value != "whole-work":
        return "source_scope must be whole-work"
    if key == "as_of":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return "as_of must be a valid Gregorian YYYY-MM-DD date"
        try:
            datetime.date.fromisoformat(value)
        except ValueError as exc:
            return "as_of is not a valid Gregorian date: " + str(exc)
    return ""


def run(ctx: Context) -> List[Finding]:
    """Require every base key and each present declared register's credit pair."""
    keys = list(BASE_KEYS)
    for register in ctx.profile.registers:
        if ctx.work.register_section(ctx.profile, register.id) is not None:
            keys.extend((register.id + "_translator", register.id + "_note"))
    result: List[Finding] = []
    for key in keys:
        value = ctx.work.front.get(key, "")
        if not value.strip():
            result.append(finding(ctx, "PRV-INCOMPLETE", "PRV-1",
                                  "missing required front-matter value", evidence={"key": key, "unit": ""}))
            continue
        cause = _invalid(key, value, ctx)
        if cause:
            result.append(finding(ctx, "PRV-INCOMPLETE", "PRV-1",
                                  "invalid required front-matter value: " + cause,
                                  evidence={"key": key, "unit": "", "value": value}))
    return result


CHECK = Check("provenance", enabled, run)
