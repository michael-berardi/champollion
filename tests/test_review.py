"""Source-language review: alignment, packets, two readings, guarded apply, records."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import unittest

from champollion.findings import ChampollionError
from champollion.format import parse_work
from champollion.review import (ReviewWork, align, apply_findings, parse_reply,
                                review_record, verify_packets, write_review_packets)
from tests.fixtures.support import TODAY, ProjectCase


def reply_bytes(obj, wrapped=False):
    body = json.dumps(obj, ensure_ascii=False)
    if wrapped:
        body = "prose before\n<<<BEGIN>>>\n```json\n" + body + "\n```\n<<<END>>>\nprose after"
    return body.encode("utf-8")


def finding(edition="plain", quote="The bird sings badly.", fix="The bird sings.",
            type="mistranslation", severity="major", source="Avis cantat.", reason="The source does not say badly."):
    return {"edition": edition, "type": type, "severity": severity, "source": source,
            "quote": quote, "fix": fix, "reason": reason}


class ReviewCase(ProjectCase):
    def setUp(self):
        super().setUp()
        self.replace_units([("One", "The sun rises.\nThe bird sings.")],
                           [("One", "The sun rises over hills.\nThe bird sings.")],
                           [("One", "The sun rises.\nThe bird sings badly.")])
        self.review_dir = self.root / "review"

    def review_work(self):
        return ReviewWork(self.work_path, self.profile(), str(self.root))

    def packets(self, piece_chars=5000):
        return write_review_packets(self.review_work(), str(self.review_dir / "packets"), piece_chars)

    def write_review_reply(self, entry, findings, wrapped=False):
        path = self.review_dir / "packets" / (entry["id"] + ".review.json")
        path.write_bytes(reply_bytes({"findings": findings}, wrapped))

    def verify(self):
        return verify_packets(self.review_work(), str(self.review_dir / "packets"), str(self.review_dir / "verify"))

    def verify_index(self):
        return json.loads((self.review_dir / "verify" / "index.json").read_text(encoding="utf-8"))

    def write_verdicts(self, verdict_for):
        for entry in self.verify_index()["pieces"]:
            proposals = [f for f in entry["findings"] if f["status"] == "proposed"]
            if not proposals:
                continue
            verdicts = [dict(verdict_for(f), n=f["n"]) for f in proposals]
            path = self.review_dir / "verify" / (entry["id"] + ".verify.json")
            path.write_bytes(reply_bytes({"verdicts": verdicts}))

    def apply(self, write=True, work=None):
        return apply_findings(work or self.review_work(), str(self.review_dir / "verify"), write=write)

    def run_pipeline(self, findings, verdict_for=None, wrapped=False):
        packets = self.packets()
        for entry in packets["pieces"]:
            self.write_review_reply(entry, findings, wrapped)
        result = self.verify()
        if verdict_for is not None:
            self.write_verdicts(verdict_for)
        return result

    def cli(self, *args, cwd=None):
        from champollion.cli import main
        output, errors = io.StringIO(), io.StringIO()
        previous = Path.cwd()
        try:
            if cwd is not None:
                os.chdir(cwd)
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                status = main(list(map(str, args)))
        finally:
            os.chdir(previous)
        return status, output.getvalue(), errors.getvalue()


class AlignmentTests(unittest.TestCase):
    def test_small_unit_is_one_exact_piece(self):
        text = "source body\n\nedition body\n"
        pieces = align(text, [(0, 12), (13, 26)], 5000)
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0]["exact"], [True])
        self.assertEqual(pieces[0]["spans"], [(0, 12), (13, 26)])

    def test_line_correspondence_cuts_exact_parallel_pieces(self):
        source = "\n".join(f"line {i} with some words" for i in range(6))
        edition = "\n".join(f"fila {i} con palabras" for i in range(6))
        text = source + "\n\n" + edition
        spans = [(0, len(source)), (len(source) + 2, len(text))]
        pieces = align(text, spans, 60)
        self.assertGreater(len(pieces), 1)
        self.assertTrue(all(p["exact"] == [True] for p in pieces))
        for piece in pieces:
            (s0, e0), (s1, e1) = piece["spans"]
            self.assertEqual(text[s0:e0].count("\n"), text[s1:e1].count("\n"))

    def test_mismatched_paragraphs_cut_proportionally_and_inexact(self):
        source = "\n\n".join(f"paragraph {i} " + "word " * 20 for i in range(4))
        edition = "\n\n".join(f"párrafo {i} " + "palabra " * 30 for i in range(2))
        text = source + "\n\n" + edition
        spans = [(0, len(source)), (len(source) + 2, len(text))]
        pieces = align(text, spans, 150)
        self.assertGreater(len(pieces), 1)
        self.assertTrue(any(p["exact"] == [False] for p in pieces))
        for piece in pieces:
            s, e = piece["spans"][1]
            self.assertGreater(e, s)
            self.assertGreaterEqual(s, spans[1][0])
            self.assertLessEqual(e, spans[1][1])

    def test_empty_edition_span_is_inexact(self):
        source = "\n\n".join(f"paragraph {i} " + "word " * 20 for i in range(4))
        text = source + "\n\n"
        pieces = align(text, [(0, len(source)), (len(text), len(text))], 150)
        self.assertTrue(all(p["exact"] == [False] for p in pieces))
        self.assertTrue(all(p["spans"][1][0] == p["spans"][1][1] for p in pieces))

    def test_nonpositive_limit_is_a_usage_error(self):
        with self.assertRaises(ChampollionError) as caught:
            align("a\n\nb", [(0, 1), (3, 4)], 0)
        self.assertEqual(caught.exception.cause, "usage")


class PacketTests(ReviewCase):
    def test_packets_are_deterministic_and_bound_to_passage_hashes(self):
        first = self.packets()
        other = write_review_packets(self.review_work(), str(self.review_dir / "again"))
        for entry, twin in zip(first["pieces"], other["pieces"]):
            a = (self.review_dir / "packets" / entry["file"]).read_bytes()
            b = (self.review_dir / "again" / twin["file"]).read_bytes()
            self.assertEqual(a, b)
        self.assertEqual((self.review_dir / "packets" / "index.json").read_bytes(),
                         (self.review_dir / "again" / "index.json").read_bytes())
        entry = first["pieces"][0]
        work = self.review_work()
        piece = work.pieces()[0]
        self.assertEqual(entry["sha256"]["original"], hashlib.sha256(work.passage(piece, 0).encode("utf-8")).hexdigest())
        self.assertEqual(entry["key"], work.key(piece))
        # Rerunning into the same directory is stable; a differing file is refused.
        self.packets()
        path = self.review_dir / "packets" / entry["file"]
        path.write_text("different", encoding="utf-8")
        with self.assertRaises(ChampollionError) as caught:
            self.packets()
        self.assertEqual(caught.exception.cause, "WRK-1")

    def test_packet_names_every_profile_register_and_the_source_edition(self):
        self.packets()
        text = (self.review_dir / "packets" / "0001-001.review.md").read_text(encoding="utf-8")
        for token in ("`musean`", "`plain`", '"original"', "<<<SOURCE>>>", "<<<BEGIN>>>", "The bird sings badly."):
            self.assertIn(token, text)

    def test_long_unit_is_cut_into_several_pieces(self):
        body = "\n\n".join(f"Paragraph {i} " + "word " * 30 for i in range(6))
        self.replace_units([("One", body)], [("One", body)], [("One", body)])
        result = self.packets(piece_chars=200)
        self.assertGreater(len(result["pieces"]), 1)
        self.assertEqual(result["piece_chars"], 200)


class ReplyParsingTests(unittest.TestCase):
    def test_tolerates_wrapper_fences_and_bare_json(self):
        obj = {"findings": []}
        for raw in (json.dumps(obj),
                    "<<<BEGIN>>>\n" + json.dumps(obj) + "\n<<<END>>>",
                    "```json\n" + json.dumps(obj) + "\n```",
                    "prose\n<<<BEGIN>>>\n```json\n" + json.dumps(obj) + "\n```\n<<<END>>>\nprose"):
            self.assertEqual(parse_reply(raw), obj)
        self.assertIsNone(parse_reply("not json"))
        self.assertIsNone(parse_reply("<<<BEGIN>>>\n{broken}\n<<<END>>>"))


class VerifyTests(ReviewCase):
    def test_findings_are_validated_and_only_locatable_proposals_get_packets(self):
        result = self.run_pipeline([
            finding(),
            finding(edition="original", quote="The bird sings.", fix="The bird sings well."),
            finding(quote="absent text", fix="other text"),
            finding(quote="same", fix="same"),
            finding(edition="unknown-register"),
        ], wrapped=True)
        self.assertEqual(result["packets"], 1)
        self.assertEqual(result["proposals"], 1)
        self.assertEqual(result["source_findings"], 1)
        self.assertEqual(result["not_located"], 1)
        self.assertEqual(len(result["invalid_findings"]), 2)
        entry = self.verify_index()["pieces"][0]
        statuses = [f["status"] for f in entry["findings"]]
        self.assertEqual(statuses, ["proposed", "source", "not-located", "invalid", "invalid"])
        packet = (self.review_dir / "verify" / entry["file"]).read_text(encoding="utf-8")
        self.assertIn("PROPOSAL 1", packet)
        self.assertNotIn("PROPOSAL 2", packet)
        self.assertIn("The bird sings badly.", packet)

    def test_unparseable_reply_is_named_and_passage_not_reviewed(self):
        packets = self.packets()
        path = self.review_dir / "packets" / (packets["pieces"][0]["id"] + ".review.json")
        path.write_text("no json here", encoding="utf-8")
        result = self.verify()
        self.assertEqual(result["packets"], 0)
        self.assertEqual(len(result["invalid_replies"]), 1)
        self.assertIn("unparseable reviewer reply",
                      [n["reason"] for n in result["not_reviewed"]])

    def test_missing_reply_marks_passage_not_reviewed(self):
        self.packets()
        result = self.verify()
        self.assertEqual(result["packets"], 0)
        self.assertEqual([n["reason"] for n in result["not_reviewed"]], ["no reviewer reply"])

    def test_stale_passage_between_packets_and_verify_is_not_reviewed(self):
        self.packets()
        self.change_text("The bird sings badly.", "The bird sings poorly.")
        result = self.verify()
        self.assertEqual(result["packets"], 0)
        self.assertEqual([n["reason"] for n in result["not_reviewed"]], ["passage changed since review"])


class ApplyTests(ReviewCase):
    def test_confirmed_finding_replaces_exactly_and_never_touches_original(self):
        before = self.work_path.read_bytes()
        self.run_pipeline([finding()], lambda f: {"verdict": "confirm", "why": "agreed"})
        result = self.apply()
        self.assertEqual(len(result["applied"]), 1)
        self.assertEqual(result["refused"], [])
        after = parse_work(self.work_path)
        self.assertEqual(after.section("Original").units[0].text, "The sun rises.\nThe bird sings.")
        self.assertEqual(after.register_section(self.profile(), "plain").units[0].text,
                         "The sun rises.\nThe bird sings.")
        self.assertEqual(after.register_section(self.profile(), "musean").units[0].text,
                         "The sun rises over hills.\nThe bird sings.")
        self.assertNotEqual(before, self.work_path.read_bytes())
        self.assertEqual(result["output"], str(self.work_path))

    def test_marker_preserving_fix_is_applied_and_marker_changing_fix_refused(self):
        self.replace_units([("One", "1. The sun rises.")], [("One", "1. The sun rises.")],
                           [("One", "1. The sun rises wrongly.")])
        self.run_pipeline([finding(quote="1. The sun rises wrongly.", fix="1. The sun rises.")],
                          lambda f: {"verdict": "confirm"})
        result = self.apply()
        self.assertEqual(len(result["applied"]), 1)
        self.assertIn("1. The sun rises.", self.work_path.read_text(encoding="utf-8"))

    def test_every_structural_refusal_reason(self):
        cases = [
            (finding(quote="The sun rises.\nThe bird sings badly.", fix="The sun rises. The bird sings badly."), "line breaks differ"),
            (finding(quote="The bird sings badly.", fix="The bird sings. " + "Padding. " * 100), "replacement far longer than the quotation"),
            (finding(quote="The bird sings badly.", fix="x"), "replacement far shorter than the quotation"),
            (finding(quote="The bird sings badly.", fix="The bird <<< sings."), "packet delimiters in the replacement"),
        ]
        for f, reason in cases:
            with self.subTest(reason=reason):
                self.setUp()
                self.run_pipeline([f], lambda v: {"verdict": "confirm"})
                result = self.apply()
                self.assertEqual(result["applied"], [])
                self.assertEqual([r["refusal"] for r in result["refused"]], [reason])

    def test_marker_and_heading_refusals(self):
        self.replace_units([("One", "1. The sun rises.")], [("One", "1. The sun rises.")],
                           [("One", "1. The sun rises wrongly.")])
        self.run_pipeline([finding(quote="1. The sun rises wrongly.", fix="2. The sun rises.")],
                          lambda f: {"verdict": "confirm"})
        result = self.apply()
        self.assertEqual([r["refusal"] for r in result["refused"]], ["reference markers differ"])
        self.setUp()
        self.replace_units([("One", "#### Sub\nThe sun rises.")], [("One", "#### Sub\nThe sun rises.")],
                           [("One", "#### Sub\nThe bird sings badly.")])
        self.run_pipeline([finding(quote="#### Sub", fix="##### Sub")], lambda f: {"verdict": "confirm"})
        result = self.apply()
        self.assertEqual([r["refusal"] for r in result["refused"]], ["headings differ"])

    def test_stale_passage_refuses_every_proposal(self):
        self.run_pipeline([finding()], lambda f: {"verdict": "confirm"})
        self.change_text("The sun rises.\nThe bird sings badly.", "The sun rises.\nThe bird sings poorly.")
        result = self.apply()
        self.assertEqual(result["applied"], [])
        self.assertEqual([r["refusal"] for r in result["refused"]], ["passage changed since review"])
        self.assertIn("passage changed since review", [n["reason"] for n in result["not_reviewed"]])

    def test_overlapping_corrections_first_wins(self):
        self.run_pipeline([finding(quote="The bird sings badly.", fix="The bird sings."),
                           finding(quote="sings badly", fix="sings softly")],
                          lambda f: {"verdict": "confirm"})
        result = self.apply()
        self.assertEqual(len(result["applied"]), 1)
        self.assertEqual([r["refusal"] for r in result["refused"]], ["overlaps an earlier correction"])
        self.assertIn("The bird sings.", self.work_path.read_text(encoding="utf-8"))

    def test_rejected_and_amended_verdicts(self):
        self.run_pipeline([finding()], lambda f: {"verdict": "reject", "why": "defensible"})
        result = self.apply()
        self.assertEqual(result["applied"], [])
        self.assertEqual(len(result["rejected"]), 1)
        self.setUp()
        self.run_pipeline([finding()], lambda f: {"verdict": "amend", "fix": "The bird sings sweetly.", "why": "better"})
        result = self.apply()
        self.assertEqual(len(result["applied"]), 1)
        self.assertIn("The bird sings sweetly.", self.work_path.read_text(encoding="utf-8"))
        self.setUp()
        self.run_pipeline([finding()], lambda f: {"verdict": "amend", "why": "no fix given"})
        result = self.apply()
        self.assertEqual(result["applied"], [])
        self.assertEqual(len(result["rejected"]), 1)

    def test_source_findings_are_recorded_and_never_applied(self):
        before = self.work_path.read_bytes()
        self.run_pipeline([finding(edition="original", quote="The bird sings.", fix="The bird sings well.")])
        result = self.apply()
        self.assertEqual(result["applied"], [])
        self.assertEqual(len(result["source_findings"]), 1)
        self.assertEqual(self.work_path.read_bytes(), before)
        resolution = next(d["resolution"] for d in result["dispositions"] if d["resolution"]["status"] == "source-finding")
        self.assertIn("editor", resolution["reason"])

    def test_missing_or_invalid_second_reader_reply_never_applies(self):
        self.run_pipeline([finding()])
        result = self.apply()
        self.assertEqual([r["refusal"] for r in result["refused"]], ["no second-reader reply"])
        path = self.review_dir / "verify" / "0001-001.verify.json"
        path.write_bytes(reply_bytes({"verdicts": [{"n": 99, "verdict": "confirm"}]}))
        result = self.apply()
        self.assertEqual([r["refusal"] for r in result["refused"]], ["invalid second-reader reply"])
        self.assertEqual(len(result["invalid_replies"]), 1)

    def test_not_located_quotation_is_refused(self):
        self.run_pipeline([finding(quote="absent text", fix="other text")])
        result = self.apply()
        self.assertEqual(result["applied"], [])
        self.assertEqual([r["refusal"] for r in result["refused"]],
                         ["quotation not found or not unique in the passage"])

    def test_dry_run_reports_without_writing(self):
        before = self.work_path.read_bytes()
        self.run_pipeline([finding()], lambda f: {"verdict": "confirm"})
        result = self.apply(write=False)
        self.assertEqual(len(result["applied"]), 1)
        self.assertIsNone(result["output"])
        self.assertEqual(self.work_path.read_bytes(), before)


class RecordTests(ReviewCase):
    def test_record_contents_and_report_acceptance(self):
        self.run_pipeline([finding(),
                           finding(edition="original", quote="The bird sings.", fix="The bird sings well.")],
                          lambda f: {"verdict": "confirm"})
        out = self.root / "records" / "review.json"
        result = review_record(self.review_work(), str(self.review_dir / "verify"),
                               "Synthetic test reviewer; machine review, not editorial approval",
                               str(out), today=TODAY)
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(record["reviewer"], "Synthetic test reviewer; machine review, not editorial approval")
        self.assertEqual(record["date"], TODAY)
        self.assertEqual(record["protocol_version"], "1.0.0")
        self.assertEqual(record["work"], "synthetic")
        self.assertEqual(record["work_sha256"], hashlib.sha256(self.work_path.read_bytes()).hexdigest())
        self.assertEqual(record["profile_fingerprint"], self.profile().fingerprint)
        self.assertEqual(record["source_sha256"], self.sources()["synthetic"]["sha256"])
        self.assertEqual(record["units"], ["One"])
        self.assertEqual(record["registers"], ["musean", "plain"])
        self.assertEqual(len(record["findings"]), len(record["resolutions"]))
        self.assertEqual({r["status"] for r in record["resolutions"]}, {"applied", "source-finding"})
        self.assertEqual(len(record["unresolved_findings"]), 1)
        self.assertEqual(record["passages_not_reviewed"], [])
        self.assertEqual(result["findings"], 2)
        # report.py accepts the record shape; the pending source finding keeps the gate blocked.
        self.record(reviews=[record])
        report = self.report()
        self.assertEqual(report["works"][0]["review_records"][0]["reviewer"], record["reviewer"])
        self.assertIn("unresolved judgement blockers", report["works"][0]["publication_gate"]["blockers"])

    def test_clean_review_record_satisfies_the_publication_gate(self):
        self.run_pipeline([])
        out = self.root / "records" / "review.json"
        review_record(self.review_work(), str(self.review_dir / "verify"),
                      "Synthetic test reviewer", str(out), today=TODAY)
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(record["findings"], [])
        self.assertEqual(record["resolutions"], [])
        self.record(reviews=[record])
        self.assertEqual(self.report()["publication_gate"]["status"], "eligible")

    def test_record_after_apply_reports_changed_passages(self):
        self.run_pipeline([finding()], lambda f: {"verdict": "confirm"})
        self.apply(write=True)
        out = self.root / "records" / "review.json"
        review_record(self.review_work(), str(self.review_dir / "verify"), "Synthetic test reviewer", str(out), today=TODAY)
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(record["units"], [])
        self.assertEqual([r["status"] for r in record["resolutions"]], ["refused"])
        self.assertEqual([n["reason"] for n in record["passages_not_reviewed"]], ["passage changed since review"])

    def test_record_lists_passages_not_reviewed(self):
        self.replace_units([("One", "The sun rises.\nThe bird sings."), ("Two", "The rain falls.")],
                           [("One", "The sun rises over hills.\nThe bird sings."), ("Two", "The rain falls.")],
                           [("One", "The sun rises.\nThe bird sings badly."), ("Two", "The rain falls.")])
        packets = self.packets()
        self.write_review_reply(packets["pieces"][0], [])
        self.verify()
        out = self.root / "records" / "review.json"
        review_record(self.review_work(), str(self.review_dir / "verify"), "Synthetic test reviewer", str(out), today=TODAY)
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(record["units"], ["One"])
        self.assertEqual([n["reason"] for n in record["passages_not_reviewed"]], ["no reviewer reply"])


class CliTests(ReviewCase):
    def cli_review(self, *args):
        return self.cli("review", *args, "--root", self.root, "--work", "works/synthetic.md")

    def test_cli_full_pipeline_exit_zero(self):
        status, output, errors = self.cli_review("packets", "--out", self.review_dir / "packets", "--json")
        self.assertEqual((status, errors), (0, ""))
        result = json.loads(output)
        for entry in result["pieces"]:
            self.write_review_reply(entry, [finding()])
        status, output, errors = self.cli_review("verify-packets", "--replies", self.review_dir / "packets",
                                                 "--out", self.review_dir / "verify", "--json")
        self.assertEqual((status, errors), (0, ""))
        self.write_verdicts(lambda f: {"verdict": "confirm"})
        status, output, errors = self.cli_review("apply", "--dry-run", "--replies", self.review_dir / "verify", "--json")
        self.assertEqual((status, errors), (0, ""))
        self.assertTrue(json.loads(output)["dry_run"])
        status, output, errors = self.cli_review("apply", "--replies", self.review_dir / "verify", "--json")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(len(json.loads(output)["applied"]), 1)
        status, output, errors = self.cli_review("record", "--replies", self.review_dir / "verify",
                                                 "--reviewer", "Synthetic test reviewer", "--out", self.root / "record.json", "--json")
        self.assertEqual((status, errors), (0, ""))
        self.assertTrue((self.root / "record.json").is_file())

    def test_cli_exit_one_for_invalid_reply_and_refused_apply(self):
        status, _, _ = self.cli_review("packets", "--out", self.review_dir / "packets")
        self.assertEqual(status, 0)
        (self.review_dir / "packets" / "0001-001.review.json").write_text("garbage", encoding="utf-8")
        status, output, errors = self.cli_review("verify-packets", "--replies", self.review_dir / "packets",
                                                 "--out", self.review_dir / "verify")
        self.assertEqual(status, 1)
        self.setUp()
        self.run_pipeline([finding(quote="The bird sings badly.", fix="x")], lambda f: {"verdict": "confirm"})
        status, output, errors = self.cli_review("apply", "--replies", self.review_dir / "verify")
        self.assertEqual(status, 1)
        self.assertIn("replacement far shorter than the quotation", output)

    def test_cli_exit_two_for_usage_io_and_schema(self):
        status, output, errors = self.cli("review")
        self.assertEqual(status, 2)
        self.assertIn("usage:", errors)
        status, output, errors = self.cli("review", "packets", "--root", self.root, "--work", "works/missing.md",
                                          "--out", self.review_dir / "p")
        self.assertEqual(status, 2)
        status, output, errors = self.cli_review("apply", "--replies", self.review_dir / "nowhere")
        self.assertEqual(status, 2)
        self.assertIn("IO:", errors)


if __name__ == "__main__":
    unittest.main()