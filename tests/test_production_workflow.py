import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autoplanner.cli import main
from autoplanner.parser import parse_page_texts
from autoplanner.production import OUTPUT_FILES
from autoplanner.production import resolve_production_reference, resolve_source_pdf


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProductionWorkflowTests(unittest.TestCase):
    def test_add_accepts_separate_year_and_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "producties"

            result = main(["add", "2627", "cinderella", "--root", str(root)])

            self.assertEqual(result, 0)
            self.assertTrue((root / "2627" / "cinderella" / "production.json").is_file())

    def test_init_creates_a_complete_production_dossier(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "producties"

            result = main(
                [
                    "init",
                    "2627-cinderella",
                    "--root",
                    str(root),
                ]
            )

            self.assertEqual(result, 0)
            directory = root / "2627" / "cinderella"
            for name in ("input", "answers", "output", "archive"):
                self.assertTrue((directory / name).is_dir())
            manifest = json.loads(
                (directory / "production.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["id"], "2627")
            self.assertEqual(manifest["title"], "Cinderella")
            self.assertEqual(manifest["status"], "intake")

    def test_generate_writes_all_concept_outputs_and_updates_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "producties"
            main(["init", "9999-test", "--root", str(root)])
            directory = root / "9999" / "test"
            pdf = directory / "input" / "planning.pdf"
            pdf.write_bytes(b"%PDF placeholder for mocked extraction")
            schedule = parse_page_texts(
                [
                    "\n".join(
                        [
                            "HNB 3 - Test",
                            "maandag 2 november 2026",
                            "Hoofdtoneel",
                            "19.30 - 22.00 Voorstelling 1",
                            "22.00 - 22.15 Afsluiten",
                        ]
                    )
                ],
                source_file=str(pdf),
            )

            with patch("autoplanner.cli.extract_schedule", return_value=schedule):
                result = main(
                    [
                        "generate",
                        "test",
                        "--root",
                        str(root),
                        "--rules",
                        str(PROJECT_ROOT / "config" / "avm_rules.json"),
                    ]
                )

            self.assertEqual(result, 0)
            for filename in OUTPUT_FILES.values():
                self.assertTrue((directory / "output" / filename).is_file())

            manifest = json.loads(
                (directory / "production.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["status"], "concept")
            control = json.loads(
                (directory / "output" / "controle.json").read_text(encoding="utf-8")
            )
            self.assertEqual(control["planning_status"], "concept")

            with (directory / "output" / "concept-rooster.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle, delimiter=";"))
            self.assertEqual({row["medewerker"] for row in rows}, {"AVM1", "AVM2"})
            self.assertEqual({row["events"] for row in rows}, {"V1"})
            self.assertIn(
                "VERPLICHTE AVM-EVENTS",
                (directory / "output" / "events.txt").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "Status: CONCEPT — HANDMATIGE CONTROLE NODIG",
                (directory / "output" / "concept-rooster.txt").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertIn(
                "Geen bekende aandachtspunten",
                (directory / "output" / "issues.txt").read_text(encoding="utf-8"),
            )

    def test_generate_all_regenerates_every_production(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "producties"
            directories = []
            schedules = []
            for slug in ("9997-alpha", "9998-beta"):
                main(["init", slug, "--root", str(root)])
                year, name = slug.split("-", maxsplit=1)
                directory = root / year / name
                directories.append(directory)
                pdf = directory / "input" / "planning.pdf"
                pdf.write_bytes(b"%PDF placeholder for mocked extraction")
                schedules.append(
                    parse_page_texts(
                        [
                            "\n".join(
                                [
                                    f"HNB 3 - {name.title()}",
                                    "maandag 2 november 2026",
                                    "Hoofdtoneel",
                                    "19.30 - 22.00 Voorstelling 1",
                                ]
                            )
                        ],
                        source_file=str(pdf),
                    )
                )

            with patch(
                "autoplanner.cli.extract_schedule", side_effect=schedules
            ) as extract:
                result = main(
                    [
                        "generate",
                        "--all",
                        "--root",
                        str(root),
                        "--rules",
                        str(PROJECT_ROOT / "config" / "avm_rules.json"),
                    ]
                )

            self.assertEqual(result, 0)
            self.assertEqual(extract.call_count, 2)
            for directory in directories:
                for filename in OUTPUT_FILES.values():
                    self.assertTrue((directory / "output" / filename).is_file())

    def test_generate_creates_answer_template_for_open_questions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "producties"
            main(["init", "9998-opera", "--root", str(root)])
            directory = root / "9998" / "opera"
            pdf = directory / "input" / "planning.pdf"
            pdf.write_bytes(b"%PDF placeholder for mocked extraction")
            schedule = parse_page_texts(
                [
                    "\n".join(
                        [
                            "DNO 4 - Testopera",
                            "maandag 2 november 2026",
                            "Hoofdtoneel",
                            "19.30 - 22.00 Voorstelling 1",
                        ]
                    )
                ],
                source_file=str(pdf),
            )

            with patch("autoplanner.cli.extract_schedule", return_value=schedule):
                main(
                    [
                        "generate",
                        str(directory),
                        "--rules",
                        str(PROJECT_ROOT / "config" / "avm_rules.json"),
                    ]
                )

            answers = json.loads(
                (directory / "answers" / "decisions.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("decor_inbouw_nodig", answers)
            manifest = json.loads(
                (directory / "production.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["status"], "invoer_nodig")

    def test_name_reference_finds_production_and_rejects_ambiguity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "producties"
            main(["add", "2627", "cinderella", "--root", str(root)])

            found = resolve_production_reference("cinderella", root)
            self.assertEqual(found, (root / "2627" / "cinderella").resolve())

            main(["add", "2728", "cinderella", "--root", str(root)])
            with self.assertRaisesRegex(ValueError, "Meerdere producties"):
                resolve_production_reference("cinderella", root)

    def test_latest_pdf_is_selected_by_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "producties"
            main(["add", "2627", "cinderella", "--root", str(root)])
            directory = root / "2627" / "cinderella"
            old_pdf = directory / "input" / "planning-v1.pdf"
            new_pdf = directory / "input" / "planning-v2.pdf"
            old_pdf.write_bytes(b"old")
            new_pdf.write_bytes(b"new")
            os.utime(old_pdf, ns=(1_000_000_000, 1_000_000_000))
            os.utime(new_pdf, ns=(2_000_000_000, 2_000_000_000))

            selected = resolve_source_pdf(directory, {})

            self.assertEqual(selected, new_pdf.resolve())


if __name__ == "__main__":
    unittest.main()
