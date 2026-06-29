import unittest
from pathlib import Path

from autoplanner.avm import apply_avm_rules, load_rules
from autoplanner.export import (
    render_avm_events_text,
    render_daily_summary_text,
    render_text,
)
from autoplanner.parser import parse_page_texts
from autoplanner.shift_planner import (
    build_cao_resolved_assignments,
    plan_daily_shifts,
    plan_daily_shifts_for_items,
    update_schedule_validation,
)
from autoplanner.rules_report import render_rules_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ParserTests(unittest.TestCase):
    def test_cross_midnight_and_metadata(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "HNB 3 - Test",
                        "Accountview nummer: 123",
                        "Planningsperiode: 2 dec 2026 - 3 dec 2026",
                        "woensdag 2 december 2026",
                        "Hoofdtoneel",
                        "23.00 - 00.30 Afbouw",
                    ]
                )
            ]
        )
        self.assertEqual(schedule.accountview_number, "123")
        self.assertEqual(schedule.items[0].end.isoformat(), "2026-12-03T00:30:00")
        self.assertEqual(schedule.items[0].location, "Hoofdtoneel")

    def test_avm_annotation_is_not_silently_assigned(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "vrijdag 4 december 2026",
                        "Hoofdtoneel",
                        "18.00 Dinerpauze",
                        "AVM",
                        "18.00 - 19.40 Belichten + video",
                    ]
                )
            ]
        )
        apply_avm_rules(
            schedule,
            {"required_text": ["AVM"], "review_text": ["video"]},
        )
        self.assertEqual(len(schedule.annotations), 1)
        self.assertTrue(schedule.annotations[0].relation_uncertain)
        self.assertEqual(schedule.items[0].avm_status, "controleren")
        self.assertEqual(schedule.items[1].avm_status, "controleren")

    def test_richten_licht_is_excluded_from_review(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "zaterdag 28 november 2026",
                        "Hoofdtoneel",
                        "18.00 - 23.00 Opbouwen/voorbereiden",
                        "Richten licht & video",
                    ]
                )
            ]
        )
        apply_avm_rules(
            schedule,
            {
                "review_text": ["video"],
                "ignore_review_text": ["richten licht"],
            },
        )
        self.assertEqual(schedule.items[0].avm_status, "niet_gemarkeerd")

    def test_details_are_preserved(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 7 december 2026",
                        "Hoofdtoneel",
                        "20.00 - 23.00 Voorgenerale orkest",
                        "bezoek statushouders",
                    ]
                )
            ]
        )
        self.assertEqual(schedule.items[0].details, ["bezoek statushouders"])

    def test_repeated_headers_and_footers_are_not_details(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 7 december 2026",
                        "Hoofdtoneel",
                        "20.00 - 23.00 Voorgenerale orkest",
                        "bezoek statushouders",
                        "HNB/26-27 HNB 3 - Cinderella",
                        "Pagina 1 van 2",
                    ]
                ),
                "\n".join(
                    [
                        "HNB 3 - Cinderella",
                        "HNB/26-27",
                        "dinsdag 8 december 2026",
                        "Hoofdtoneel",
                        "08.00 - 10.00 Technische tijd",
                    ]
                ),
            ]
        )
        self.assertEqual(schedule.items[0].details, ["bezoek statushouders"])

    def test_staffing_rules_require_two_for_supported_activities(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "woensdag 9 december 2026",
                        "Hoofdtoneel",
                        "15.00 - 16.00 Voorbereiden voorstelling",
                        "19.30 - 22.00 Voorstelling 1",
                        "22.15 - 23.00 Voorgenerale orkest",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "voorstelling",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "required_count": 2,
                },
                {
                    "id": "voorgenerale",
                    "activity_patterns": [r"^voorgenerale(?:\s+.*)?$"],
                    "required_count": 2,
                },
            ],
            "call_time_rules": [
                {
                    "id": "1930",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "activity_start": "19:30",
                    "call_time": "15:00",
                }
            ],
            "shift_planning": {
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "special_shift_rules": [
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "activity_start": "14:00",
                        "start": "10:00",
                        "end": "18:00",
                    },
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "start_offset_minutes": -270,
                        "end_offset_minutes": 240,
                    }
                ],
            },
        }
        apply_avm_rules(schedule, rules)

        preparation, performance, rehearsal = schedule.items
        self.assertEqual(preparation.avm_required_count, 0)
        self.assertEqual(performance.avm_required_count, 2)
        self.assertEqual(performance.avm_status, "vereist")
        self.assertEqual(performance.avm_call_time.isoformat(), "2026-12-09T15:00:00")
        self.assertEqual(rehearsal.avm_required_count, 2)

        text = render_text(schedule, rules)
        self.assertIn("ROOSTER AVM1", text)
        self.assertIn("ROOSTER AVM2", text)
        self.assertIn("wo 09-12-2026", text)
        self.assertIn("Datum", text)
        self.assertIn("| Tijd", text)
        self.assertIn("events", text)
        self.assertIn("wo 09-12-2026 | 15:00-00:00 | 09u00", text)
        self.assertEqual(text.count("V1 19:30-22:00"), 2)
        self.assertNotIn("VST 1", text)
        self.assertIn("VGO", text)
        self.assertNotIn("Voorbereiden voorstelling", text)

    def test_call_time_at_noon_is_adjusted_to_1130(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "zondag 20 december 2026",
                        "Hoofdtoneel",
                        "14.00 - 16.50 Voorstelling 8",
                    ]
                )
            ]
        )
        apply_avm_rules(
            schedule,
            {
                "staffing_rules": [
                    {
                        "id": "voorstelling",
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "required_count": 2,
                    }
                ],
                "call_time_rules": [
                    {
                        "id": "test-aanwezigheid",
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "activity_start": "14:00",
                        "call_time": "12:00",
                    }
                ],
                "call_time_adjustments": [
                    {
                        "id": "geen-dienststart-om-1200",
                        "from": "12:00",
                        "to": "11:30",
                    }
                ],
            },
        )
        item = schedule.items[0]
        self.assertEqual(item.start.strftime("%H:%M"), "14:00")
        self.assertEqual(item.avm_call_time.strftime("%H:%M"), "11:30")
        self.assertIn("Dienststartcorrectie", " ".join(item.avm_reasons))

    def test_performance_and_general_have_three_work_hours_before_them(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "zondag 20 december 2026",
                        "Hoofdtoneel",
                        "12.30 Lunchpauze",
                        "14.00 - 16.50 Voorstelling 8",
                        "maandag 21 december 2026",
                        "Hoofdtoneel",
                        "17.30 Dinerpauze",
                        "20.00 - 23.00 Generale repetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "voorstelling",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "required_count": 2,
                },
                {
                    "id": "generale",
                    "activity_patterns": [r"^generale\s+repetitie$"],
                    "required_count": 2,
                },
            ],
            "call_time_rules": [
                {
                    "id": "drie-werkuren-vooraf",
                    "activity_patterns": [
                        r"^voorstelling(?:\s+\d+)?$",
                        r"^generale\s+repetitie$",
                    ],
                    "working_minutes_before": 180,
                    "excluded_break_minutes": {
                        "lunchpauze": 30,
                        "dinerpauze": 60,
                    },
                }
            ],
            "call_time_adjustments": [
                {
                    "id": "geen-start-om-1200",
                    "from": "12:00",
                    "to": "11:30",
                }
            ],
        }
        apply_avm_rules(schedule, rules)

        performance = next(item for item in schedule.items if item.activity == "Voorstelling 8")
        general = next(item for item in schedule.items if item.activity == "Generale repetitie")
        self.assertEqual(performance.avm_call_time.strftime("%H:%M"), "10:30")
        self.assertEqual(general.avm_call_time.strftime("%H:%M"), "16:00")

    def test_school_performance_at_1330_starts_at_ten_for_lunch_and_three_work_hours(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 14 december 2026",
                        "Hoofdtoneel",
                        "12.00 Lunchpauze",
                        "13.30 - 15.30 Schoolvoorstelling",
                        "23.00 - 00.30 Afbouw",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        shift = plan_daily_shifts(schedule, "AVM1", rules)[0]
        self.assertEqual(shift.start.strftime("%H:%M"), "10:00")
        self.assertEqual(shift.end.strftime("%H:%M"), "18:00")
        self.assertEqual(shift.duration_minutes, 480)

    def test_default_double_performance_rule_keeps_both_primary_avms_on_both_shows(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 14 december 2026",
                        "Hoofdtoneel",
                        "13.30 - 15.30 Schoolvoorstelling",
                        "20.00 - 22.50 Voorstelling 4",
                        "23.00 - 00.30 Afbouw",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        assignments = build_cao_resolved_assignments(schedule, rules)
        self.assertEqual(set(assignments), {"AVM1", "AVM2"})
        for position in ("AVM1", "AVM2"):
            self.assertEqual(
                [item.activity for item in assignments[position]],
                ["Schoolvoorstelling", "Voorstelling 4"],
            )
            shift = plan_daily_shifts_for_items(
                position, assignments[position], rules
            )[0]
            self.assertEqual(shift.start.strftime("%H:%M"), "12:00")
            self.assertEqual(shift.end.strftime("%H:%M"), "00:00")
            self.assertEqual(shift.duration_minutes, 720)
            self.assertFalse(any("CAO-CONFLICT" in flag for flag in shift.flags))

    def test_technical_and_cd_rehearsals_prefer_avm1(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "dinsdag 1 december 2026",
                        "Hoofdtoneel",
                        "14.30 - 17.30 Technische repetitie",
                        "19.15 - 19.55 Cd toneelrepetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "technische-repetitie",
                    "activity_patterns": [r"^technische\s+repetitie(?:\s+.*)?$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                },
                {
                    "id": "cd-toneelrepetitie",
                    "activity_patterns": [r"^cd\s+toneelrepetitie(?:\s+.*)?$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                    "flexible_positions": ["AVM1", "AVM2"],
                },
            ]
        }
        apply_avm_rules(schedule, rules)

        self.assertTrue(all(item.avm_required_count == 1 for item in schedule.items))
        self.assertTrue(
            all(item.avm_preferred_position == "AVM1" for item in schedule.items)
        )
        text = render_text(schedule)
        avm1_text, avm2_text = text.split("ROOSTER AVM2", maxsplit=1)
        self.assertIn("TR 14:30-17:30", avm1_text)
        self.assertIn("CD 19:15-19:55", avm1_text)
        self.assertNotIn("TR 14:30-17:30", avm2_text)

    def test_cd_rehearsal_moves_to_avm2_when_avm1_day_is_longer(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "dinsdag 1 december 2026",
                        "Hoofdtoneel",
                        "14.30 - 17.30 Technische repetitie",
                        "19.15 - 19.55 Cd toneelrepetitie",
                        "20.00 - 23.00 Piano toneelrepetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "technische-repetitie",
                    "activity_patterns": [r"^technische\s+repetitie$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                },
                {
                    "id": "cd-toneelrepetitie",
                    "activity_patterns": [r"^cd\s+toneelrepetitie$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                    "flexible_positions": ["AVM1", "AVM2"],
                },
                {
                    "id": "piano-toneelrepetitie",
                    "activity_patterns": [r"^piano\s+toneelrepetitie$"],
                    "required_count": 2,
                },
            ],
            "shift_planning": {
                "target_minutes": 480,
                "post_activity_minutes": 30,
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
        }
        apply_avm_rules(schedule, rules)
        avm1_items = plan_daily_shifts(schedule, "AVM1", rules)[0].items
        avm2_items = plan_daily_shifts(schedule, "AVM2", rules)[0].items

        self.assertNotIn("Cd toneelrepetitie", [item.activity for item in avm1_items])
        self.assertIn("Cd toneelrepetitie", [item.activity for item in avm2_items])

    def test_belichten_requires_one_avm_and_defaults_to_avm2(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "woensdag 2 december 2026",
                        "Hoofdtoneel",
                        "10.00 - 12.15 Belichten + video",
                        "12.15 - 12.45 Richten licht & video",
                    ]
                )
            ]
        )
        apply_avm_rules(
            schedule,
            {
                "staffing_rules": [
                    {
                        "id": "belichten",
                        "activity_patterns": [r"\bbelichten\b"],
                        "required_count": 1,
                        "maximum_count": 1,
                        "flexible_positions": ["AVM2", "AVM1"],
                    }
                ],
                "review_text": ["video"],
                "ignore_review_text": ["richten licht"],
            },
        )

        belichten, richten = schedule.items
        self.assertEqual(belichten.avm_required_count, 1)
        self.assertEqual(belichten.avm_maximum_count, 1)
        self.assertIsNone(belichten.avm_preferred_position)
        self.assertEqual(belichten.avm_flexible_positions, ["AVM2", "AVM1"])
        self.assertEqual(richten.avm_status, "niet_gemarkeerd")
        text = render_text(schedule)
        avm1_text, avm2_text = text.split("ROOSTER AVM2", maxsplit=1)
        self.assertNotIn("BEL 10:00-12:15", avm1_text)
        self.assertIn("BEL 10:00-12:15", avm2_text)
        self.assertIn("wo 02-12-2026 | 09:00-17:00 | 08u00", text)
        self.assertIn("BEL 10:00-12:15", text)

    def test_dno_preparing_belichten_is_an_avm1_preparation_day(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "DNO 4 - Testopera",
                        "vrijdag 4 december 2026",
                        "Hoofdtoneel",
                        "08.00 - 12.15 Opbouwen/voorbereiden belichten",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        self.assertEqual(schedule.items[0].avm_preferred_position, "AVM1")
        shift = plan_daily_shifts(schedule, "AVM1", rules)[0]
        self.assertEqual(shift.start.strftime("%H:%M"), "07:00")
        self.assertEqual(shift.end.strftime("%H:%M"), "15:00")

    def test_default_rules_use_half_hour_wrap_time_for_belichten_sr_and_ptr(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "vrijdag 4 december 2026",
                        "Hoofdtoneel",
                        "16.00 - 17.00 Opbouwen/voorbereiden belichten",
                        "zaterdag 5 december 2026",
                        "Hoofdtoneel",
                        "16.00 - 17.00 Solistenrepetitie",
                        "zondag 6 december 2026",
                        "Hoofdtoneel",
                        "16.00 - 17.00 Piano toneelrepetitie",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        shifts = [
            *plan_daily_shifts(schedule, "AVM1", rules),
            *plan_daily_shifts(schedule, "AVM2", rules),
        ]
        expected_activities = {
            "Solistenrepetitie",
            "Piano toneelrepetitie",
        }
        checked_activities = set()
        for shift in shifts:
            for item in shift.items:
                if item.activity not in expected_activities:
                    continue
                checked_activities.add(item.activity)
                self.assertEqual(
                    shift.end.strftime("%H:%M"),
                    "17:30",
                    msg=f"{item.activity} should only keep AVM 30 minutes after afloop",
                )

        self.assertEqual(checked_activities, expected_activities)

    def test_vgo_uses_half_hour_load_out_when_staying_on_stage(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 7 december 2026",
                        "Hoofdtoneel",
                        "20.00 - 23.00 Voorgenerale orkest",
                        "23.00 - 23.15 Afsluiten",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        shift = plan_daily_shifts(schedule, "AVM1", rules)[0]
        self.assertEqual(shift.start.strftime("%H:%M"), "15:30")
        self.assertEqual(shift.end.strftime("%H:%M"), "23:30")
        self.assertEqual(shift.duration_minutes, 480)
        self.assertEqual(shift.target_minutes, 480)
        self.assertFalse(any("streefduur" in flag for flag in shift.flags))

    def test_roster_bounds_round_outward_without_preserving_target_duration(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 7 december 2026",
                        "Hoofdtoneel",
                        "13.10 - 16.10 Technische repetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "technische-repetitie",
                    "activity_patterns": [r"^technische\s+repetitie$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                }
            ],
            "shift_planning": {
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "round_shift_boundaries_minutes": 30,
            },
        }
        apply_avm_rules(schedule, rules)

        shift = plan_daily_shifts(schedule, "AVM1", rules)[0]
        self.assertEqual(shift.start.strftime("%H:%M"), "09:00")
        self.assertEqual(shift.end.strftime("%H:%M"), "17:30")
        self.assertEqual(shift.duration_minutes, 510)
        self.assertFalse(any("streefduur" in flag for flag in shift.flags))

    def test_short_shift_is_extended_to_target_and_reported(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 7 december 2026",
                        "Hoofdtoneel",
                        "13.00 - 16.00 Technische repetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "technische-repetitie",
                    "activity_patterns": [r"^technische\s+repetitie$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                }
            ],
            "shift_planning": {
                "target_minutes": 480,
                "default_shift_start": "10:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "round_shift_boundaries_minutes": 30,
            },
        }
        apply_avm_rules(schedule, rules)

        shift = plan_daily_shifts(schedule, "AVM1", rules)[0]
        self.assertEqual(shift.start.strftime("%H:%M"), "10:00")
        self.assertEqual(shift.end.strftime("%H:%M"), "18:00")
        self.assertEqual(shift.duration_minutes, 480)
        self.assertIn(
            "Dienst aangevuld met 60 min tot streefduur van 8u00",
            shift.flags,
        )

    def test_long_belichten_event_is_split_between_avm1_and_avm2(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "woensdag 2 december 2026",
                        "Hoofdtoneel",
                        "09.00 - 19.00 Belichten",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "belichten",
                    "activity_patterns": [r"\bbelichten\b"],
                    "required_count": 1,
                    "flexible_positions": ["AVM2", "AVM1"],
                }
            ],
            "shift_planning": {
                "target_minutes": 480,
                "post_activity_minutes": 30,
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
        }
        apply_avm_rules(schedule, rules)
        avm1 = plan_daily_shifts(schedule, "AVM1", rules)
        avm2 = plan_daily_shifts(schedule, "AVM2", rules)

        self.assertEqual(len(avm1[0].items), 1)
        self.assertEqual(len(avm2[0].items), 1)
        intervals = sorted(
            (shift.items[0].start.strftime("%H:%M"), shift.items[0].end.strftime("%H:%M"))
            for shift in (avm1[0], avm2[0])
        )
        self.assertEqual(intervals, [("09:00", "14:00"), ("14:00", "19:00")])

    def test_configured_two_person_activity_requires_both_avm_positions(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "dinsdag 1 december 2026",
                        "Hoofdtoneel",
                        "20.00 - 23.00 Generale repetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "generale",
                    "activity_patterns": [r"^generale(?:\s+repetitie)?$"],
                    "required_count": 2,
                }
            ],
            "review_text": ["video"],
        }
        apply_avm_rules(schedule, rules)

        item = schedule.items[0]
        self.assertEqual(item.avm_required_count, 2)
        self.assertEqual(item.avm_status, "vereist")
        self.assertEqual(len(plan_daily_shifts(schedule, "AVM1", rules)), 1)
        self.assertEqual(len(plan_daily_shifts(schedule, "AVM2", rules)), 1)

    def test_default_rules_keep_cd_and_bel_single_staffed_and_ptr_double_staffed(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "dinsdag 1 december 2026",
                        "Hoofdtoneel",
                        "10.00 - 12.00 Belichten + video",
                        "14.30 - 17.30 Technische repetitie",
                        "19.15 - 19.55 Cd toneelrepetitie",
                        "20.00 - 23.00 Piano toneelrepetitie + licht + video",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        by_activity = {item.activity: item for item in schedule.items}
        self.assertEqual(by_activity["Belichten + video"].avm_required_count, 1)
        self.assertFalse(by_activity["Belichten + video"].avm_optional)
        self.assertFalse(by_activity["Belichten + video"].non_avm_allowed)
        self.assertEqual(by_activity["Cd toneelrepetitie"].avm_required_count, 1)
        self.assertEqual(
            by_activity["Piano toneelrepetitie + licht + video"].avm_required_count,
            2,
        )
        self.assertEqual(by_activity["Technische repetitie"].avm_required_count, 1)
        self.assertFalse(
            any(
                "Locatiebezettingsregel" in reason
                for activity in (
                    "Belichten + video",
                    "Cd toneelrepetitie",
                )
                for reason in by_activity[activity].avm_reasons
            )
        )
        self.assertFalse(
            any(
                "Locatiebezettingsregel" in reason
                for reason in by_activity[
                    "Piano toneelrepetitie + licht + video"
                ].avm_reasons
            )
        )

    def test_orchestra_and_soloist_rehearsals_require_both_avm_positions(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 7 december 2026",
                        "Hoofdtoneel",
                        "16.30 - 18.00 Orkestrepetitie",
                        "18.00 - 19.00 Solistenrepetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                    {
                        "id": "orkestrepetitie",
                        "activity_patterns": [r"^orkestrepetitie(?:\s+.*)?$"],
                        "required_count": 2,
                    },
                {
                        "id": "solistenrepetitie",
                        "activity_patterns": [r"^solistenrepetitie(?:\s+.*)?$"],
                        "required_count": 2,
                },
            ]
        }
        apply_avm_rules(schedule, rules)

        self.assertTrue(all(item.avm_required_count == 2 for item in schedule.items))
        total_assigned = sum(
            len(plan_daily_shifts(schedule, position, rules)[0].items)
            for position in ("AVM1", "AVM2")
            if plan_daily_shifts(schedule, position, rules)
        )
        self.assertEqual(total_assigned, 4)

    def test_pvg_activity_code_is_rendered(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "donderdag 3 december 2026",
                        "Hoofdtoneel",
                        "19.30 - 22.30 Piano Voorgenerale",
                    ]
                )
            ]
        )
        apply_avm_rules(
            schedule,
            {
                "staffing_rules": [
                    {
                        "id": "test-pvg",
                        "activity_patterns": [r"^piano\s+voorgenerale$"],
                        "required_count": 2,
                    }
                ]
            },
        )
        self.assertIn("PVG 19:30-22:30", render_text(schedule))

    def test_daily_summary_uses_compact_performance_codes(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "woensdag 9 december 2026",
                        "Hoofdtoneel",
                        "14.00 - 16.50 Voorstelling 1",
                        "18.00 - 19.00 Solistenrepetitie",
                        "20.00 - 22.50 Voorstelling 2",
                    ]
                )
            ]
        )
        apply_avm_rules(
            schedule,
            {
                "staffing_rules": [
                    {
                        "id": "voorstelling",
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "required_count": 2,
                    },
                    {
                        "id": "solistenrepetitie",
                        "activity_patterns": [r"^solistenrepetitie(?:\s+.*)?$"],
                        "required_count": 2,
                    },
                ]
            },
        )

        text = render_daily_summary_text(schedule)
        self.assertIn("Datum", text)
        self.assertIn("events", text)
        self.assertNotIn("Afkortingen", text)
        self.assertIn("wo 09-12-2026", text)
        self.assertIn("14:00-22:50", text)
        self.assertIn("08u50", text)
        self.assertIn("V1, V2, SR", text)
        self.assertIn(
            "V1 14:00-16:50; SR 18:00-19:00; V2 20:00-22:50",
            text,
        )
        self.assertNotIn("VST 1", text)

    def test_events_column_uses_configured_code_order(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "woensdag 9 december 2026",
                        "Hoofdtoneel",
                        "10.00 - 10.30 Belichten",
                        "10.30 - 11.00 Cd toneelrepetitie",
                        "11.00 - 11.30 Piano toneelrepetitie",
                        "11.30 - 12.00 Technische repetitie",
                        "12.00 - 12.30 Solistenrepetitie",
                        "12.30 - 13.00 Orkestrepetitie",
                        "13.00 - 13.30 Orkesttoneelrepetitie",
                        "13.30 - 14.00 Voorgenerale orkest",
                        "14.00 - 14.30 Generale repetitie",
                        "14.30 - 15.00 Voorstelling 1",
                    ]
                )
            ]
        )
        apply_avm_rules(schedule, load_rules(PROJECT_ROOT / "config" / "avm_rules.json"))

        text = render_daily_summary_text(schedule)
        self.assertIn("V1, GEN, VGO, OTR, OR, TR, PTR, SR, CD, BEL", text)
        self.assertIn(
            "BEL 10:00-10:30; CD 10:30-11:00; PTR 11:00-11:30; "
            "TR 11:30-12:00; SR 12:00-12:30; OR 12:30-13:00; "
            "OTR 13:00-13:30; VGO 13:30-14:00; GEN 14:00-14:30; "
            "V1 14:30-15:00",
            text,
        )

    def test_impossible_rest_between_relative_show_shifts_is_flagged(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "zaterdag 19 december 2026",
                        "Hoofdtoneel",
                        "20.00 - 22.50 Voorstelling 7",
                        "zondag 20 december 2026",
                        "Hoofdtoneel",
                        "14.00 - 16.50 Voorstelling 8",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "voorstellingen",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "required_count": 2,
                }
            ],
            "shift_planning": {
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "special_shift_rules": [
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "activity_start": "14:00",
                        "start": "10:00",
                        "end": "18:00",
                    },
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "start_offset_minutes": -270,
                        "end_offset_minutes": 240,
                    }
                ],
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
        }
        apply_avm_rules(schedule, rules)
        shifts = plan_daily_shifts(schedule, "AVM1", rules)

        self.assertEqual(shifts[0].end.strftime("%H:%M"), "00:00")
        self.assertEqual(shifts[1].start.strftime("%H:%M"), "11:00")
        self.assertTrue(any("Start verschoven" in flag for flag in shifts[1].flags))
        self.assertFalse(any("CAO-CONFLICT" in flag for flag in shifts[1].flags))

    def test_text_roster_adds_team_avm_to_resolve_cao_conflicts(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 21 december 2026",
                        "Hoofdtoneel",
                        "14.00 - 16.50 Voorstelling 9",
                        "20.00 - 22.50 Voorstelling 10",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "voorstellingen",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "required_count": 2,
                }
            ],
            "shift_planning": {
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "special_shift_rules": [
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "activity_start": "14:00",
                        "start": "10:00",
                        "end": "18:00",
                    },
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "start_offset_minutes": -270,
                        "end_offset_minutes": 240,
                    },
                ],
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
            "overflow_policy": {
                "allow_team_replacement": True,
                "replacement_label": "TEAM-AVM",
                "trigger_on_cao_conflict": True,
                "allow_required_activity_replacement_when_needed": True,
            },
        }
        apply_avm_rules(schedule, rules)

        text = render_text(schedule, rules)
        self.assertIn("ROOSTER TEAM-AVM1", text)
        self.assertIn("ROOSTER TEAM-AVM2", text)
        self.assertIn("V10 20:00-22:50", text)
        self.assertNotIn("CAO-CONFLICT", text)

    def test_team_avm_never_replaces_all_primary_performance_positions(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 21 december 2026",
                        "Hoofdtoneel",
                        "14.00 - 16.50 Voorstelling 9",
                        "20.00 - 22.50 Voorstelling 10",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "voorstellingen",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "required_count": 2,
                }
            ],
            "shift_planning": {
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "special_shift_rules": [
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "activity_start": "14:00",
                        "start": "10:00",
                        "end": "18:00",
                    },
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "start_offset_minutes": -270,
                        "end_offset_minutes": 240,
                    },
                ],
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
            "overflow_policy": {
                "allow_team_replacement": True,
                "replacement_label": "TEAM-AVM",
                "trigger_on_cao_conflict": True,
                "allow_required_activity_replacement_when_needed": True,
                "primary_presence_activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
            },
        }
        apply_avm_rules(schedule, rules)

        assignments = build_cao_resolved_assignments(schedule, rules)
        primary_positions_by_activity = {}
        for position in ("AVM1", "AVM2"):
            for item in assignments[position]:
                primary_positions_by_activity.setdefault(item.activity, set()).add(position)

        self.assertTrue(primary_positions_by_activity["Voorstelling 9"])
        self.assertTrue(primary_positions_by_activity["Voorstelling 10"])

    def test_fixed_primary_events_are_not_moved_to_team_avm(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 21 december 2026",
                        "Hoofdtoneel",
                        "14.00 - 16.50 Voorstelling 9",
                        "20.00 - 22.50 Voorstelling 10",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "voorstellingen",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "required_count": 2,
                }
            ],
            "shift_planning": {
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "special_shift_rules": [
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "activity_start": "14:00",
                        "start": "10:00",
                        "end": "18:00",
                    },
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "start_offset_minutes": -270,
                        "end_offset_minutes": 240,
                    },
                ],
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
            "overflow_policy": {
                "allow_team_replacement": True,
                "replacement_label": "TEAM-AVM",
                "trigger_on_cao_conflict": True,
                "allow_required_activity_replacement_when_needed": True,
                "fixed_primary_activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
            },
        }
        apply_avm_rules(schedule, rules)

        assignments = build_cao_resolved_assignments(schedule, rules)
        for activity in ("Voorstelling 9", "Voorstelling 10"):
            for position in ("AVM1", "AVM2"):
                self.assertTrue(
                    any(item.activity == activity for item in assignments[position])
                )
            self.assertFalse(
                any(
                    item.activity == activity
                    for position, items in assignments.items()
                    if position.startswith("TEAM-AVM")
                    for item in items
                )
            )

    def test_longer_cao_compliant_shift_is_preferred_over_team_replacement(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "vrijdag 4 december 2026",
                        "Hoofdtoneel",
                        "10.00 - 12.00 Technische repetitie",
                        "17.00 - 19.00 Orkestrepetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "technische-repetitie",
                    "activity_patterns": [r"^technische\s+repetitie$"],
                    "required_count": 2,
                },
                {
                    "id": "orkestrepetitie",
                    "activity_patterns": [r"^orkestrepetitie$"],
                    "required_count": 2,
                },
            ],
            "shift_planning": {
                "target_minutes": 480,
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
            "overflow_policy": {
                "allow_team_replacement": True,
                "trigger_on_cao_conflict": True,
                "allow_required_activity_replacement_when_needed": True,
            },
        }
        apply_avm_rules(schedule, rules)

        assignments = build_cao_resolved_assignments(schedule, rules)
        self.assertEqual(set(assignments), {"AVM1", "AVM2"})
        for position in ("AVM1", "AVM2"):
            shift = plan_daily_shifts_for_items(
                position, assignments[position], rules
            )[0]
            self.assertEqual(shift.duration_minutes, 660)
            self.assertFalse(any("CAO-CONFLICT" in flag for flag in shift.flags))

    def test_noon_start_adjustment_is_skipped_when_it_would_exceed_twelve_hours(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "woensdag 2 december 2026",
                        "Hoofdtoneel",
                        "13.00 - 16.30 Piano toneelrepetitie",
                        "20.00 - 23.00 Piano toneelrepetitie",
                        "23.00 - 00.30 Afbouw",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        shift = plan_daily_shifts(schedule, "AVM1", rules)[0]
        self.assertEqual(shift.start.strftime("%H:%M"), "12:00")
        self.assertEqual(shift.end.strftime("%H:%M"), "00:00")
        self.assertEqual(shift.duration_minutes, 720)
        self.assertTrue(
            any("Startcorrectie vervallen" in flag for flag in shift.flags)
        )
        self.assertFalse(any("CAO-CONFLICT" in flag for flag in shift.flags))

    def test_cao_replacement_prefers_low_priority_events_over_otr(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "vrijdag 4 december 2026",
                        "Hoofdtoneel",
                        "12.15 - 12.45 Cd toneelrepetitie",
                        "13.00 - 16.00 Piano toneelrepetitie + licht + video",
                        "16.00 - 17.00 Belichten + video",
                        "16.30 - 18.00 Orkestrepetitie",
                        "18.00 - 19.40 Belichten + video",
                        "20.00 - 23.00 Orkest toneelrepetitie + licht + video",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        assignments = build_cao_resolved_assignments(schedule, rules)
        avm1_activities = [item.activity for item in assignments["AVM1"]]
        team_activities = [
            item.activity
            for position, items in assignments.items()
            if position.startswith("TEAM-AVM")
            for item in items
        ]

        self.assertIn("Orkest toneelrepetitie + licht + video", avm1_activities)
        self.assertNotIn("Orkest toneelrepetitie + licht + video", team_activities)
        self.assertTrue(
            any(
                activity.startswith(("Belichten", "Cd toneelrepetitie", "Piano toneelrepetitie"))
                for activity in team_activities
            )
        )

    def test_avm_event_overview_separates_required_and_review(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 7 december 2026",
                        "Hoofdtoneel",
                        "20.00 - 23.00 Voorgenerale orkest",
                        "18.30 - 19.40 Licht/decorcorrecties",
                        "video controleren",
                        "23.00 - 23.30 Afbouw",
                    ]
                )
            ]
        )
        apply_avm_rules(
            schedule,
            {
                "staffing_rules": [
                    {
                        "id": "vgo",
                        "activity_patterns": [r"^voorgenerale\s+orkest$"],
                        "required_count": 2,
                    }
                ],
                "review_text": ["video"],
            },
        )
        text = render_avm_events_text(schedule)
        self.assertIn("VERPLICHTE AVM-EVENTS (1)", text)
        self.assertIn("Code | Activiteit", text)
        self.assertIn("VGO  | Voorgenerale orkest", text)
        self.assertIn("NOG TE BEOORDELEN AVM-KANDIDATEN (1)", text)
        self.assertIn("GEEN AVM NODIG (1)", text)
        self.assertIn("Afbouw", text)

    def test_avm_event_overview_uses_short_production_name(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "HNB 3 - Test",
                        "maandag 7 december 2026",
                        "Hoofdtoneel",
                        "20.00 - 23.00 Technische repetitie",
                    ]
                )
            ]
        )
        apply_avm_rules(
            schedule,
            {
                "staffing_rules": [
                    {
                        "id": "techniek",
                        "activity_patterns": [r"^technische\s+repetitie$"],
                        "required_count": 1,
                    }
                ],
            },
        )
        text = render_avm_events_text(schedule)
        self.assertIn("Naam van de productie: Test", text)
        self.assertRegex(text, r"Test\s+\| TR")
        self.assertNotIn("HNB 3 - Test", text)

    def test_rules_report_contains_business_and_cao_rules(self):
        text = render_rules_text(
            {
                "staffing_rules": [
                    {
                        "id": "voorstelling",
                        "description": "Een voorstelling vereist twee AVM'ers.",
                        "required_count": 2,
                    }
                ],
                "call_time_rules": [
                    {"description": "Vierenhalf uur voor aanvang aanwezig."}
                ],
                "shift_planning": {
                    "target_minutes": 480,
                    "post_activity_minutes": 30,
                    "maximum_shift_minutes": 720,
                    "minimum_rest_minutes": 660,
                },
            },
            {
                "source": "CAO.pdf",
                "rules": [
                    {
                        "type": "minimum_rest_minutes_between_days",
                        "value": 660,
                        "source_article": "Artikel 13 lid 3",
                        "source_page": 13,
                    }
                ],
            },
        )
        self.assertIn("AVM1 leidt de productie", text)
        self.assertIn("Standaarddienst: 09:00-17:00", text)
        self.assertIn("Minimale rust tussen werkdagen: 11u00", text)

    def test_performance_shift_is_relative_to_start_time(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "woensdag 9 december 2026",
                        "Hoofdtoneel",
                        "20.00 - 22.50 Voorstelling 1",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "voorstelling",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "required_count": 2,
                }
            ],
            "shift_planning": {
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "special_shift_rules": [
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "start_offset_minutes": -270,
                        "end_offset_minutes": 240,
                    }
                ],
            },
        }
        apply_avm_rules(schedule, rules)
        shift = plan_daily_shifts(schedule, "AVM1", rules)[0]
        self.assertEqual(shift.start.strftime("%H:%M"), "15:30")
        self.assertEqual(shift.end.strftime("%H:%M"), "00:00")

    def test_ordinary_activity_uses_or_shifts_nine_to_five_block(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "woensdag 2 december 2026",
                        "Hoofdtoneel",
                        "18.00 - 20.00 Technische repetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "technische-repetitie",
                    "activity_patterns": [r"^technische\s+repetitie$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                }
            ],
            "shift_planning": {
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
            },
        }
        apply_avm_rules(schedule, rules)
        shift = plan_daily_shifts(schedule, "AVM1", rules)[0]
        self.assertEqual(shift.start.strftime("%H:%M"), "13:00")
        self.assertEqual(shift.end.strftime("%H:%M"), "21:00")

    def test_main_stage_required_activity_is_upgraded_to_two_avms(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "dinsdag 1 december 2026",
                        "Hoofdtoneel",
                        "14.30 - 17.30 Technische repetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "technische-repetitie",
                    "activity_patterns": [r"^technische\s+repetitie$"],
                    "required_count": 1,
                }
            ],
            "location_staffing_rules": [
                {
                    "id": "hoofdtoneel-dubbel",
                    "location_patterns": [r"^Hoofdtoneel$"],
                    "apply_when_avm_required": True,
                    "exclude_activity_patterns": [r"\bbelichten\b"],
                    "required_count": 2,
                }
            ],
        }
        apply_avm_rules(schedule, rules)
        self.assertEqual(schedule.items[0].avm_required_count, 2)

    def test_optional_belichten_only_uses_avm_when_it_fits_existing_shift(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "woensdag 9 december 2026",
                        "Hoofdtoneel",
                        "09.00 - 10.00 Belichten",
                        "16.30 - 17.30 Belichten",
                        "20.00 - 22.50 Voorstelling 1",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "belichten",
                    "activity_patterns": [r"\bbelichten\b"],
                    "required_count": 0,
                    "maximum_count": 1,
                    "optional_avm": True,
                    "non_avm_allowed": True,
                    "flexible_positions": ["AVM2", "AVM1"],
                },
                {
                    "id": "voorstelling",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "required_count": 2,
                },
            ],
            "shift_planning": {
                "default_shift_start": "09:00",
                "default_shift_end": "17:00",
                "activity_buffer_before_minutes": 60,
                "activity_buffer_after_minutes": 60,
                "special_shift_rules": [
                    {
                        "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                        "start_offset_minutes": -270,
                        "end_offset_minutes": 240,
                    }
                ],
            },
        }
        apply_avm_rules(schedule, rules)
        assignments = {
            position: [
                item.activity for item in plan_daily_shifts(schedule, position, rules)[0].items
            ]
            for position in ("AVM1", "AVM2")
        }
        self.assertEqual(
            sum(activities.count("Belichten") for activities in assignments.values()), 1
        )
        self.assertTrue(
            any("Belichten" in activities for activities in assignments.values())
        )

    def test_cao_conflict_requests_team_avm_replacement(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 21 december 2026",
                        "Hoofdtoneel",
                        "09.00 - 11.00 Voorstelling 1",
                        "20.00 - 23.00 Voorstelling 2",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "voorstelling",
                    "activity_patterns": [r"^voorstelling(?:\s+\d+)?$"],
                    "required_count": 2,
                }
            ],
            "shift_planning": {
                "target_minutes": 480,
                "post_activity_minutes": 30,
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
            "overflow_policy": {
                "allow_team_replacement": True,
                "replacement_label": "TEAM-AVM",
                "trigger_on_cao_conflict": True,
            },
        }
        apply_avm_rules(schedule, rules)
        flags = plan_daily_shifts(schedule, "AVM1", rules)[0].flags
        self.assertIn("TEAM-AVM OVERNAME NODIG", flags)

    def test_cao_team_replacement_can_be_limited_to_piano_and_belichten(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 21 december 2026",
                        "Hoofdtoneel",
                        "09.00 - 10.00 Belichten",
                        "20.00 - 23.00 Piano toneelrepetitie",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "belichten",
                    "activity_patterns": [r"\bbelichten\b"],
                    "required_count": 1,
                    "flexible_positions": ["AVM1"],
                },
                {
                    "id": "piano",
                    "activity_patterns": [r"^piano\s+toneelrepetitie$"],
                    "required_count": 1,
                    "flexible_positions": ["AVM1"],
                },
            ],
            "shift_planning": {
                "target_minutes": 480,
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
            "overflow_policy": {
                "allow_team_replacement": True,
                "replacement_label": "TEAM-AVM",
                "trigger_on_cao_conflict": True,
                "replaceable_activity_patterns": [
                    r"\bbelichten\b",
                    r"^piano\s+toneelrepetitie$",
                ],
            },
        }
        apply_avm_rules(schedule, rules)
        flags = plan_daily_shifts(schedule, "AVM1", rules)[0].flags
        self.assertIn(
            "TEAM-AVM OVERNAME NODIG VOOR: Belichten, Piano toneelrepetitie",
            flags,
        )

    def test_validated_jonna_rules_are_applied_to_dno_schedule(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "DNO 4 - Testopera",
                        "maandag 2 november 2026",
                        "Studio 1",
                        "09.00 - 12.00 Piano toneelrepetitie",
                        "13.00 - 16.00 Grote studio repetitie",
                        "dinsdag 3 november 2026",
                        "Foyer",
                        "09.00 - 10.00 OT meeting",
                        "10.00 - 11.00 Cast & Huis Presentatie",
                        "woensdag 4 november 2026",
                        "Montagehal",
                        "09.00 - 12.00 Inbouwen in het decor",
                        "donderdag 5 november 2026",
                        "Hoofdtoneel",
                        "09.00 - 12.00 Opbouwen/voorbereiden belichten",
                        "inbouw in het decor",
                        "13.00 - 14.00 Technische tijd",
                        "14.00 - 16.00 Licht richten",
                        "16.00 - 18.00 Belichten",
                        "19.00 - 22.00 Regierepetitie",
                        "vrijdag 6 november 2026",
                        "Hoofdtoneel",
                        "09.00 - 10.00 Oplevering van het decor",
                        "10.00 - 13.00 Piano CD",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)
        items = {item.activity: item for item in schedule.items}

        self.assertEqual(schedule.title, "DNO 4 - Testopera")
        self.assertEqual(items["Piano toneelrepetitie"].avm_required_count, 0)
        self.assertEqual(items["Grote studio repetitie"].avm_required_count, 1)
        self.assertEqual(items["OT meeting"].avm_preferred_position, "AVM1")
        self.assertTrue(
            any("uitnodiging" in reason for reason in items["OT meeting"].avm_reasons)
        )
        self.assertEqual(items["Cast & Huis Presentatie"].avm_required_count, 1)
        self.assertEqual(items["Inbouwen in het decor"].avm_required_count, 1)
        self.assertEqual(
            items["Opbouwen/voorbereiden belichten"].avm_required_count, 2
        )
        self.assertEqual(items["Technische tijd"].avm_required_count, 0)
        self.assertEqual(items["Licht richten"].avm_required_count, 0)
        self.assertEqual(items["Belichten"].avm_required_count, 1)
        self.assertEqual(
            items["Belichten"].avm_call_time.strftime("%H:%M"), "15:30"
        )
        self.assertEqual(items["Regierepetitie"].avm_required_count, 1)
        self.assertEqual(
            items["Regierepetitie"].avm_call_time.strftime("%H:%M"), "18:00"
        )
        self.assertEqual(
            items["Oplevering van het decor"].avm_planning_level, "richtlijn"
        )
        self.assertEqual(items["Oplevering van het decor"].avm_status, "richtlijn")
        self.assertEqual(items["Piano CD"].avm_required_count, 2)

    def test_dno_without_decor_answer_stays_blocked_on_question(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "DNO 4 - Testopera",
                        "donderdag 5 november 2026",
                        "Hoofdtoneel",
                        "16.00 - 18.00 Belichten",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)
        update_schedule_validation(schedule, rules)

        question = next(
            question
            for question in schedule.decision_questions
            if question.id == "decor_inbouw_nodig"
        )
        self.assertTrue(question.is_open)
        self.assertEqual(schedule.planning_status, "invoer_nodig")
        self.assertTrue(
            any("Moet er" in reason for reason in schedule.blocking_reasons)
        )

    def test_yes_answer_generates_required_montagehal_moment(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "DNO 4 - Testopera",
                        "donderdag 5 november 2026",
                        "Hoofdtoneel",
                        "16.00 - 18.00 Belichten",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(
            schedule,
            rules,
            {
                "decor_inbouw_nodig": {
                    "value": "ja",
                    "day": "2026-11-04",
                    "start": "09:00",
                    "end": "12:00",
                }
            },
        )
        update_schedule_validation(schedule, rules)

        generated = next(
            item for item in schedule.items if item.activity == "Decorinbouw"
        )
        self.assertEqual(generated.location, "Montagehal")
        self.assertEqual(generated.avm_required_count, 1)
        self.assertEqual(generated.avm_planning_level, "verplicht")
        self.assertEqual(
            schedule.planning_requirements[0].status, "ingepland"
        )
        self.assertFalse(
            any("Montagehal" in reason for reason in schedule.blocking_reasons)
        )

    def test_unresolved_cao_conflict_marks_schedule_invalid(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 21 december 2026",
                        "Hoofdtoneel",
                        "09.00 - 11.00 Vast moment",
                        "20.00 - 23.00 Vast moment",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "vast",
                    "activity_patterns": [r"^vast moment$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                }
            ],
            "shift_planning": {
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
            "overflow_policy": {
                "allow_team_replacement": False,
                "fixed_primary_activity_patterns": [r"^vast moment$"],
            },
        }
        apply_avm_rules(schedule, rules)
        update_schedule_validation(schedule, rules)

        self.assertEqual(schedule.planning_status, "ongeldig_cao")
        self.assertTrue(schedule.cao_conflicts)

    def test_guideline_is_kept_before_customary_moment(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "maandag 21 december 2026",
                        "Hoofdtoneel",
                        "09.00 - 10.00 Richtlijnmoment",
                        "20.00 - 21.00 Gebruikelijk moment",
                    ]
                )
            ]
        )
        rules = {
            "staffing_rules": [
                {
                    "id": "richtlijn",
                    "activity_patterns": [r"^richtlijnmoment$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                    "planning_level": "richtlijn",
                },
                {
                    "id": "gebruikelijk",
                    "activity_patterns": [r"^gebruikelijk moment$"],
                    "required_count": 1,
                    "preferred_position": "AVM1",
                    "planning_level": "gebruikelijk",
                },
            ],
            "shift_planning": {
                "maximum_shift_minutes": 720,
                "minimum_rest_minutes": 660,
            },
        }
        apply_avm_rules(schedule, rules)
        update_schedule_validation(schedule, rules)
        items = {item.activity: item for item in schedule.items}

        self.assertEqual(
            items["Richtlijnmoment"].avm_assignment_status, "ingepland"
        )
        self.assertEqual(
            items["Gebruikelijk moment"].avm_assignment_status,
            "niet_ingepland",
        )
        self.assertIn(
            "CAO-conflict",
            items["Gebruikelijk moment"].avm_omission_reason,
        )

    def test_regular_rules_start_on_first_main_stage_day(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "HNB 3 - Test",
                        "maandag 2 november 2026",
                        "Muziektheater",
                        "19.00 - 22.00 Voorstelling 1",
                        "dinsdag 3 november 2026",
                        "Hoofdtoneel",
                        "19.00 - 22.00 Voorstelling 2",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        self.assertEqual(schedule.items[0].avm_required_count, 0)
        self.assertIn("Buiten AVM-roosterperiode", schedule.items[0].avm_reasons[0])
        self.assertEqual(schedule.items[1].avm_required_count, 2)

    def test_hnb_required_rehearsals_apply_on_main_stage(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "HNB 3 - Testballet",
                        "maandag 2 november 2026",
                        "Hoofdtoneel",
                        "10.00 - 13.00 Piano toneelrepetitie",
                        "13.00 - 13.30 Cd toneelrepetitie",
                        "14.00 - 15.00 Solistenrepetitie",
                        "15.00 - 16.00 Orkestrepetitie",
                        "16.00 - 17.00 Orkest toneelrepetitie",
                        "17.00 - 18.00 Toneelrepetitie",
                        "18.00 - 19.00 Generale repetitie",
                        "19.00 - 22.00 Voorstelling 1"
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        by_activity = {item.activity: item for item in schedule.items}
        self.assertEqual(by_activity["Piano toneelrepetitie"].avm_required_count, 2)
        self.assertEqual(by_activity["Cd toneelrepetitie"].avm_required_count, 1)
        self.assertEqual(by_activity["Solistenrepetitie"].avm_required_count, 2)
        self.assertEqual(by_activity["Orkestrepetitie"].avm_required_count, 2)
        self.assertEqual(
            by_activity["Orkest toneelrepetitie"].avm_required_count, 2
        )
        self.assertEqual(by_activity["Toneelrepetitie"].avm_required_count, 0)
        self.assertEqual(by_activity["Generale repetitie"].avm_required_count, 2)
        self.assertEqual(by_activity["Voorstelling 1"].avm_required_count, 2)

    def test_hnb_rehearsals_in_large_studio_require_no_avm(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "HNB 3 - Testballet",
                        "maandag 2 november 2026",
                        "Grote Studio",
                        "10.00 - 11.00 Piano toneelrepetitie",
                        "11.00 - 12.00 Cd toneelrepetitie",
                        "12.00 - 13.00 Solistenrepetitie",
                        "13.00 - 14.00 Orkestrepetitie",
                        "14.00 - 15.00 Orkest toneelrepetitie",
                        "15.00 - 16.00 Generale repetitie",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)

        self.assertTrue(
            all(item.avm_required_count == 0 for item in schedule.items)
        )
        self.assertTrue(
            all(
                any("overige-studiorepetities" in reason for reason in item.avm_reasons)
                for item in schedule.items
            )
        )

    def test_closing_marker_controls_end_of_avm_shift(self):
        schedule = parse_page_texts(
            [
                "\n".join(
                    [
                        "DNO 4 - Testopera",
                        "maandag 2 november 2026",
                        "Hoofdtoneel",
                        "19.00 - 22.00 Voorstelling 1",
                        "22.00 - 22.15 Afsluiten",
                        "dinsdag 3 november 2026",
                        "Hoofdtoneel",
                        "19.00 - 22.00 Voorstelling 2",
                        "22.00 - 23.30 Afbouw",
                    ]
                )
            ]
        )
        rules = load_rules(PROJECT_ROOT / "config" / "avm_rules.json")
        apply_avm_rules(schedule, rules)
        shifts = plan_daily_shifts(schedule, "AVM1", rules)

        self.assertEqual(shifts[0].end.strftime("%H:%M"), "22:30")
        self.assertEqual(shifts[1].end.strftime("%H:%M"), "23:00")
        self.assertEqual(schedule.items[0].avm_day_wrap_minutes, 30)

        text = render_text(schedule, rules)
        self.assertIn("Overstaan", text)
        rows = [
            [column.strip() for column in line.split("|")]
            for line in text.splitlines()
            if line.startswith(("ma 02-11-2026", "di 03-11-2026"))
        ]
        self.assertEqual(rows[0][5], "x")
        self.assertEqual(rows[1][5], "")
        self.assertEqual(schedule.items[2].avm_day_wrap_minutes, 60)


if __name__ == "__main__":
    unittest.main()
