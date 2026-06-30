from __future__ import annotations

from pathlib import Path


def _hours(minutes: int) -> str:
    return f"{minutes // 60}u{minutes % 60:02d}"


def _positions(rule: dict) -> str:
    if rule.get("optional_avm") and rule.get("non_avm_allowed"):
        return "0-1 AVM'er; niet-AVM-dekking toegestaan; maximaal 1 AVM tegelijk"
    if int(rule.get("required_count", 0)) >= 2:
        return "AVM1 + AVM2"
    if rule.get("preferred_position") and rule.get("flexible_positions"):
        return (
            f"1 AVM'er; voorkeur {rule['preferred_position']}, flexibel over "
            + "/".join(rule["flexible_positions"])
        )
    if rule.get("preferred_position"):
        return f"1 AVM'er; voorkeur {rule['preferred_position']}"
    if rule.get("flexible_positions"):
        maximum = "; maximaal 1 tegelijk" if rule.get("maximum_count") == 1 else ""
        return (
            "1 AVM'er; flexibel over "
            + "/".join(rule["flexible_positions"])
            + maximum
        )
    return f"{rule.get('required_count', 1)} AVM'er(s)"


CAO_DESCRIPTIONS = {
    "maximum_work_minutes_per_week": "Maximale arbeidstijd per week",
    "minimum_rest_minutes_between_days": "Minimale rust tussen werkdagen",
    "minimum_continuous_rest_minutes_per_calendar_week": "Minimale aaneengesloten wekelijkse rust",
    "target_work_minutes_per_four_weeks_fulltime": "Norm per vier weken bij fulltime",
    "maximum_scheduled_minutes_per_four_weeks_fulltime": "Maximumrooster per vier weken bij fulltime",
    "minimum_scheduled_minutes_per_four_weeks_fulltime": "Minimumrooster per vier weken bij fulltime",
    "minimum_shift_minutes": "Minimale dienstduur",
    "split_shift_allowed": "Gebroken dienst toegestaan",
    "dinner_break_minutes_range": "Dinerpauze",
    "minimum_free_days_per_four_weeks": "Minimumaantal vrije dagen per vier weken",
    "maximum_consecutive_work_days": "Maximumaantal opeenvolgende werkdagen",
    "maximum_days_up_to_twelve_hours_per_week": "Maximumaantal werkdagen tot twaalf uur per week",
}


def _cao_value(rule: dict) -> str:
    rule_type = rule.get("type")
    if rule_type == "split_shift_allowed":
        return "nee" if rule.get("value") is False else "ja"
    if rule_type == "dinner_break_minutes_range":
        return f"{rule['minimum']}-{rule['maximum']} minuten"
    if "minutes" in str(rule_type):
        return _hours(int(rule["value"]))
    if rule_type == "maximum_days_up_to_twelve_hours_per_week":
        return f"{rule['value']} dagen; maximaal {_hours(rule['maximum_shift_minutes'])} per dienst"
    return str(rule.get("value", ""))


def render_rules_text(avm_rules: dict, cao_rules: dict) -> str:
    shift = avm_rules.get("shift_planning", {})
    lines = [
        "ROOSTERREGELS AVM",
        "==================",
        "",
        "1. Rollen en verdeling",
        "----------------------",
        "- AVM1 leidt de productie.",
        "- Activiteiten met bezetting 2 staan bij AVM1 en AVM2.",
        "- Flexibele enkelbezette activiteiten worden verdeeld om diensten zo dicht mogelijk bij 8 uur te houden.",
        "- Een flexibel activiteitblok langer dan 8 uur mag in twee aansluitende delen over AVM1 en AVM2 worden verdeeld.",
        "- Een voorkeur voor AVM1 geldt alleen als AVM2 daardoor geen duidelijk betere dagduur krijgt.",
        "- Een langere dienst voor AVM1/AVM2 heeft voorrang op TEAM-AVM zolang de harde CAO-grenzen behouden blijven.",
        "- Alleen als AVM1 of AVM2 anders een CAO-conflict krijgt, voegt het rooster TEAM-AVM-diensten toe.",
        "- Voorstellingen blijven altijd bij AVM1 en AVM2 en worden niet door TEAM-AVM overgenomen.",
        "",
        "2. AVM-bezetting per activiteit",
        "--------------------------------",
    ]
    scope = avm_rules.get("planning_scope", {})
    if scope:
        lines.append(f"- {scope.get('description', 'AVM-roosterperiode is begrensd.')}")
    for level, description in avm_rules.get("planning_levels", {}).items():
        lines.append(f"- Planniveau {level}: {description}")
    for rule in avm_rules.get("exclusion_rules", []):
        lines.append(
            f"- {rule.get('description', rule.get('id', 'Uitsluitingsregel'))}"
        )
    for rule in avm_rules.get("staffing_rules", []):
        lines.append(
            f"- {rule.get('description', rule.get('id', 'regel'))} [{_positions(rule)}]"
        )
    for rule in avm_rules.get("location_staffing_rules", []):
        lines.append(f"- {rule.get('description', rule.get('id', 'locatieregel'))}")
    overflow = avm_rules.get("overflow_policy", {})
    if overflow:
        lines.append(f"- {overflow.get('description', 'Teamvervanging toegestaan.')}")

    lines.extend(["", "3. Aanwezigheidstijden", "------------------------"])
    for rule in avm_rules.get("call_time_rules", []):
        lines.append(f"- {rule.get('description', rule.get('id', 'regel'))}")
    for adjustment in avm_rules.get("call_time_adjustments", []):
        lines.append(f"- {adjustment.get('description', adjustment.get('id', 'correctie'))}")

    lines.extend(
        [
            "",
            "4. Opbouw van een dagdienst — automatisch actief",
            "--------------------------------------------------",
            f"- Standaarddienst: {shift.get('default_shift_start', '09:00')}-{shift.get('default_shift_end', '17:00')}.",
            f"- Gewone activiteiten worden afgedekt vanaf {shift.get('activity_buffer_before_minutes', 60)} minuten voor aanvang tot {shift.get('activity_buffer_after_minutes', 60)} minuten na afloop; bij overstaan wordt een uitloop van 60 minuten altijd 30 minuten.",
            "- Als het vereiste venster niet in de standaarddienst past, wordt het blok verschoven.",
            "- De start kan later worden gezet om de minimale nachtrust te behouden, zolang alle activiteiten nog worden afgedekt.",
            f"- Diensten boven {_hours(int(shift.get('maximum_shift_minutes', 720)))} worden opgelost via TEAM-AVM of, als dat niet lukt, als CAO-conflict gemarkeerd.",
            f"- Minder dan {_hours(int(shift.get('minimum_rest_minutes', 660)))} rust tussen diensten wordt opgelost via TEAM-AVM of, als dat niet lukt, als CAO-conflict gemarkeerd.",
            "- Afwijkingen van de streefduur worden niet als opmerking in het rooster getoond.",
            "",
            "5. Detectie en uitzonderingen",
            "-----------------------------",
            "- Mogelijke aanvullende AVM-termen: "
            + ", ".join(avm_rules.get("review_text", []))
            + ". Deze worden ter beoordeling gemarkeerd.",
            "- Geen AVM nodig bij: "
            + ", ".join(avm_rules.get("ignore_review_text", []))
            + ".",
            "- Losse AVM-notities uit de PDF worden niet automatisch aan een activiteit gekoppeld.",
            "- Een onbeantwoorde blokkerende productievraag houdt het rooster op de status CONCEPT — INVOER NODIG.",
            "",
            "6. Afkortingen in het rooster",
            "------------------------------",
            "BEL = Belichten | CD = Cd-toneelrepetitie | GEN = Generale",
            "OR = Orkestrepetitie | OTR = Orkesttoneelrepetitie | ZIT = Zit/Sitzprobe",
            "PTR = Pianotoneelrepetitie | PTR/CD = Piano-/cd-toneelrepetitie",
            "PVG = Pianovoorgenerale | SR = Solistenrepetitie | SV = Schoolvoorstelling",
            "TR = Technische repetitie | VGO = Voorgenerale orkest | V1/V2/... = Voorstelling",
            "",
            "7. CAO-regels",
            "--------------",
            f"Bron: {cao_rules.get('source', 'onbekend')}",
        ]
    )
    for question in avm_rules.get("conditional_questions", []):
        lines.insert(
            lines.index("- Een onbeantwoorde blokkerende productievraag houdt het rooster op de status CONCEPT — INVOER NODIG."),
            f"- Conditionele vraag: {question.get('prompt', question.get('id', 'onbekend'))}",
        )
    for buffer_rule in shift.get("activity_buffer_rules", []):
        lines.insert(
            lines.index("- Als het vereiste venster niet in de standaarddienst past, wordt het blok verschoven."),
            f"- {buffer_rule.get('description', buffer_rule.get('id', 'Afwijkende bufferregel'))}",
        )
    for closing_rule in shift.get("day_closing_rules", []):
        lines.insert(
            lines.index("- Als het vereiste venster niet in de standaarddienst past, wordt het blok verschoven."),
            f"- {closing_rule.get('description', closing_rule.get('id', 'Dagafsluitingsregel'))}",
        )
    for special_rule in shift.get("special_shift_rules", []):
        lines.insert(
            lines.index("- De start kan later worden gezet om de minimale nachtrust te behouden, zolang alle activiteiten nog worden afgedekt."),
            f"- {special_rule.get('description', 'Afwijkende dienstregel')}",
        )
    for rule in cao_rules.get("rules", []):
        description = CAO_DESCRIPTIONS.get(rule.get("type"), rule.get("type", "regel"))
        lines.append(
            f"- {description}: {_cao_value(rule)} "
            f"({rule.get('source_article', 'bron onbekend')}, pagina {rule.get('source_page', '?')})."
        )

    lines.extend(
        [
            "",
            "8. Nog niet volledig automatisch controleerbaar",
            "------------------------------------------------",
            "De volgende regels vereisen een compleet persoonlijk rooster, contractomvang en werkzaamheden buiten deze productie:",
            "- weekmaximum en weektotalen;",
            "- normen, bandbreedte en vrije dagen per vier weken;",
            "- maximaal zeven opeenvolgende werkdagen;",
            "- vrij weekend en overige wekelijkse rust;",
            "- pauzes en uitsluiting van gebroken diensten;",
            "- maximumaantal twaalfuursdagen per week.",
            "Deze punten staan in de configuratie, maar moeten voorlopig handmatig worden gecontroleerd.",
            "Een conflict met een reeds controleerbare CAO-regel maakt het conceptrooster ongeldig; het wordt niet als definitief rooster aangemerkt.",
            "",
        ]
    )
    return "\n".join(lines)


def write_rules_text(avm_rules: dict, cao_rules: dict, target: str | Path) -> None:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_rules_text(avm_rules, cao_rules), encoding="utf-8")
