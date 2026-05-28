"""Pure functions for extracting display data from Canvas command structures."""

import re
from typing import Any

SCHEMA_KEY_LABELS: dict[str, str] = {
    "reasonForVisit": "Chief Complaint",
    "hpi": "History of Present Illness",
    "assess": "Assessment & Plan",
    "plan": "Plan",
    "diagnose": "Diagnose",
    "prescribe": "Prescribe",
    "medicationStatement": "Medication Statement",
    "allergy": "Allergy",
    "familyHistory": "Family History",
    "medicalHistory": "Past Medical History",
    "surgicalHistory": "Past Surgical History",
    "instruct": "Instruct",
    "goal": "Goal",
    "closeGoal": "Close Goal",
    "updateGoal": "Update Goal",
    "perform": "Perform",
    "vitals": "Vitals",
    "physicalExam": "Physical Exam",
    "reviewOfSystems": "Review of Systems",
    "questionnaire": "Questionnaire",
    "labOrder": "Lab Order",
    "imagingOrder": "Image",
    "refer": "Refer",
    "task": "Task",
    "followUp": "Follow Up",
    "updateDiagnosis": "Change Diagnosis",
    "removeAllergy": "Remove Allergy",
    "stopMedication": "Stop Medication",
    "changeMedication": "Change Medication",
    "adjustPrescription": "Adjust Prescription",
    "refill": "Refill",
    "resolveCondition": "Resolve Condition",
    "historyReview": "History Review",
    "chartReview": "Chart Review",
    "chartSectionReview": "Reviewed",
    "labReview": "Lab Results Review",
    "imagingReview": "Imaging Report Review",
    "referralReview": "Consult Report Review",
    "uncategorizedDocumentReview": "Document Review",
    "educationalMaterial": "Educational Material",
    "immunize": "Immunization",
    "immunizationStatement": "Immunization Statement",
    "pocLabTest": "Point-of-Care Lab Test",
    "structuredAssessment": "Structured Assessment",
    "adjustDiagnosis": "Adjust Diagnosis",
    "adjustProtocol": "Adjust Protocol",
    "approveChange": "Approve Change",
    "approveRefill": "Approve Refill",
    "denyChange": "Deny Change",
    "denyRefill": "Deny Refill",
    "snoozeProtocol": "Snooze Protocol",
    "reference": "Reference",
    "visualExamFinding": "Visual Exam Finding",
    "ros": "Review of Systems",
    "exam": "Physical Exam",
}

# Maps schema_key to SOAP section, matching Canvas Note tab grouping.
# Section display order: SUBJECTIVE, HISTORY, OBJECTIVE, ASSESSMENT & PLAN, CHARGES
SOAP_SECTIONS: dict[str, str] = {
    "reasonForVisit": "SUBJECTIVE",
    "hpi": "SUBJECTIVE",
    "reviewOfSystems": "SUBJECTIVE",
    "ros": "SUBJECTIVE",
    "medicalHistory": "HISTORY",
    "surgicalHistory": "HISTORY",
    "familyHistory": "HISTORY",
    "historyReview": "HISTORY",
    "vitals": "OBJECTIVE",
    "physicalExam": "OBJECTIVE",
    "exam": "OBJECTIVE",
    "questionnaire": "OBJECTIVE",
    "pocLabTest": "OBJECTIVE",
    "visualExamFinding": "OBJECTIVE",
    "chartReview": "OBJECTIVE",
    "chartSectionReview": "OBJECTIVE",
    "medicationStatement": "OBJECTIVE",
    "allergy": "OBJECTIVE",
    "assess": "ASSESSMENT & PLAN",
    "diagnose": "ASSESSMENT & PLAN",
    "plan": "ASSESSMENT & PLAN",
    "prescribe": "ASSESSMENT & PLAN",
    "labOrder": "ASSESSMENT & PLAN",
    "imagingOrder": "ASSESSMENT & PLAN",
    "refer": "ASSESSMENT & PLAN",
    "followUp": "ASSESSMENT & PLAN",
    "instruct": "ASSESSMENT & PLAN",
    "task": "ASSESSMENT & PLAN",
    "goal": "ASSESSMENT & PLAN",
    "closeGoal": "ASSESSMENT & PLAN",
    "updateGoal": "ASSESSMENT & PLAN",
    "perform": "CHARGES",
    "stopMedication": "ASSESSMENT & PLAN",
    "changeMedication": "ASSESSMENT & PLAN",
    "adjustPrescription": "ASSESSMENT & PLAN",
    "refill": "ASSESSMENT & PLAN",
    "removeAllergy": "ASSESSMENT & PLAN",
    "immunize": "ASSESSMENT & PLAN",
    "immunizationStatement": "ASSESSMENT & PLAN",
    "educationalMaterial": "ASSESSMENT & PLAN",
    "approveChange": "ASSESSMENT & PLAN",
    "approveRefill": "ASSESSMENT & PLAN",
    "denyChange": "ASSESSMENT & PLAN",
    "denyRefill": "ASSESSMENT & PLAN",
    "snoozeProtocol": "ASSESSMENT & PLAN",
    "adjustProtocol": "ASSESSMENT & PLAN",
    "reference": "ASSESSMENT & PLAN",
    "updateDiagnosis": "ASSESSMENT & PLAN",
    "resolveCondition": "ASSESSMENT & PLAN",
    "adjustDiagnosis": "ASSESSMENT & PLAN",
    "structuredAssessment": "ASSESSMENT & PLAN",
    "labReview": "ASSESSMENT & PLAN",
    "imagingReview": "ASSESSMENT & PLAN",
    "referralReview": "ASSESSMENT & PLAN",
    "uncategorizedDocumentReview": "ASSESSMENT & PLAN",
}

SECTION_ORDER = ["SUBJECTIVE", "HISTORY", "OBJECTIVE", "ASSESSMENT & PLAN", "CHARGES"]

BP_SITE_LABELS: dict[int, str] = {
    0: "Sitting, Right Upper Arm",
    1: "Sitting, Left Upper Arm",
    2: "Sitting, Right Lower Arm",
    3: "Sitting, Left Lower Arm",
    4: "Standing, Right Upper Arm",
    5: "Standing, Left Upper Arm",
    6: "Standing, Right Lower Arm",
    7: "Standing, Left Lower Arm",
    8: "Supine, Right Upper Arm",
    9: "Supine, Left Upper Arm",
    10: "Supine, Right Lower Arm",
    11: "Supine, Left Lower Arm",
}


def _schema_key_to_label(schema_key: str) -> str:
    if schema_key in SCHEMA_KEY_LABELS:
        return SCHEMA_KEY_LABELS[schema_key]
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", schema_key)
    return spaced.title()


def _format_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits[0] == "1":
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return raw


def _safe_str(val: Any) -> str:
    """Convert to string, treating None as empty."""
    if val is None:
        return ""
    return str(val)


def _extract_date_str(val: Any) -> str:
    """Extract a date string from a value that may be a string or dict.

    Canvas sometimes stores dates as dicts like {'date': '2026-04-14', 'input': '2026-04-14'}.
    """
    if val is None:
        return ""
    if isinstance(val, dict):
        return str(val.get("date") or val.get("input") or "")
    return str(val) if val else ""


def _format_date(raw: Any) -> str:
    """Format an ISO date string or date dict to MM/DD/YYYY."""
    date_str = _extract_date_str(raw) if isinstance(raw, dict) else (_safe_str(raw))
    if not date_str:
        return ""
    try:
        from datetime import date as dt_date

        d = dt_date.fromisoformat(date_str)
        return d.strftime("%m/%d/%Y")
    except (ValueError, TypeError):
        return date_str


def _get_field_text(data: dict[str, Any], field: str) -> str:
    val = data.get(field)
    if val and "text" in val:
        return str(val["text"])
    if val and "display" in val:
        return str(val["display"])
    return ""


def _format_icd_code(raw: str) -> str:
    code = raw.replace(".", "").strip().upper()
    if len(code) > 3:
        return code[:3] + "." + code[3:]
    return code


def _sanitize_html(html: str) -> str:
    """Strip dangerous HTML elements and normalize bold markers."""
    clean = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"\s+on\w+\s*=\s*[\"'][^\"']*[\"']", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+on\w+\s*=\s*\S+", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<(iframe|object|embed|form|input)[^>]*>.*?</\1>", "", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<(iframe|object|embed|form|input)[^>]*/?>", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", clean)

    def _deemphasize_label(m: re.Match[str]) -> str:
        label = m.group(1).strip()
        if label.rstrip(":").isupper():
            return label.title()
        return m.group(0)

    clean = re.sub(r"<(?:strong|b)[^>]*>([A-Z][A-Z /]+:?)</(?:strong|b)>", _deemphasize_label, clean)
    return clean


def _decode_b64_html(encoded: str) -> str:
    from base64 import b64decode

    try:
        raw = b64decode(encoded).decode("utf-8")
    except Exception:
        return ""
    return _sanitize_html(raw)


def extract_command_display(schema_key: str, data: dict[str, Any], command_display: str = "") -> dict[str, Any]:
    label = _schema_key_to_label(schema_key)
    content = ""
    html_content = ""

    if schema_key in ("hpi", "plan", "instruct"):
        content = _safe_str(data.get("narrative"))

    elif schema_key == "reasonForVisit":
        coding = _get_field_text(data, "coding")
        comment = _safe_str(data.get("comment"))
        parts = [p for p in (coding, comment) if p]
        content = "\n".join(parts)

    elif schema_key == "assess":
        raw_icd = _safe_str(data.get("icd10_code"))
        if not raw_icd:
            coding_field = data.get("coding")
            if isinstance(coding_field, dict):
                raw_icd = _safe_str(coding_field.get("value"))
        assess_icd_code = _format_icd_code(raw_icd) if raw_icd else ""
        assess_display = ""
        coding_field = data.get("coding")
        if isinstance(coding_field, dict):
            assess_display = _safe_str(coding_field.get("text"))
        elif isinstance(coding_field, str) and coding_field:
            assess_display = coding_field
        if not assess_display:
            assess_display = command_display
        assessment_text = _safe_str(data.get("narrative"))
        assess_assessment_lines = (
            [line for line in assessment_text.split("\n") if line.strip()] if assessment_text else []
        )
        header = f"{assess_icd_code} {assess_display}".strip() if assess_icd_code else assess_display
        parts = [p for p in (header, assessment_text) if p]
        content = "\n".join(parts)

    elif schema_key == "diagnose":
        raw_icd = _safe_str(data.get("icd10_code"))
        if not raw_icd:
            dx_field = data.get("diagnose")
            if isinstance(dx_field, dict):
                raw_icd = _safe_str(dx_field.get("value"))
        dx_icd_code = _format_icd_code(raw_icd) if raw_icd else ""
        dx_display = _safe_str(data.get("icd10_display"))
        if not dx_display:
            dx_display = _safe_str(data.get("condition_header"))
        if not dx_display:
            dx_field = data.get("diagnose")
            if isinstance(dx_field, dict):
                dx_display = _safe_str(dx_field.get("text"))
        if not dx_display:
            dx_display = _get_field_text(data, "coding")
        if not dx_display:
            dx_display = command_display
        header = f"{dx_icd_code} {dx_display}".strip() if dx_icd_code else dx_display
        assessment_text = _safe_str(data.get("today_assessment") or data.get("narrative"))
        dx_assessment_lines = [line for line in assessment_text.split("\n") if line.strip()] if assessment_text else []
        parts = [p for p in (header, assessment_text) if p]
        content = "\n".join(parts)

    elif schema_key == "allergy":
        name = _safe_str(data.get("allergy_text")) or _get_field_text(data, "allergy") or command_display
        detail_parts = [p for p in (
            _safe_str(data.get("reaction")),
            _safe_str(data.get("severity")),
        ) if p]
        details = " · ".join(detail_parts)
        if not details:
            details = _safe_str(data.get("narrative"))
        parts = [p for p in (name, details) if p]
        content = "\n".join(parts)

    elif schema_key == "medicationStatement":
        med_name = (
            _safe_str(data.get("medication_text"))
            or _get_field_text(data, "fdb_code")
            or _get_field_text(data, "medication")
            or command_display
        )
        med_sig = _safe_str(data.get("sig"))
        parts = [p for p in (med_name, med_sig) if p]
        content = "\n".join(parts)

    elif schema_key == "perform":
        perform_cpt = _safe_str(data.get("cpt_code"))
        perform_desc = _safe_str(data.get("description"))
        perform_notes = _safe_str(data.get("notes"))
        perf_field = data.get("perform")
        if isinstance(perf_field, dict):
            if not perform_cpt:
                perform_cpt = _safe_str(perf_field.get("value"))
            if not perform_desc:
                extra = perf_field.get("extra")
                if isinstance(extra, dict):
                    codings = extra.get("coding", [])
                    if codings and isinstance(codings, list) and isinstance(codings[0], dict):
                        perform_desc = _safe_str(codings[0].get("display"))
                if not perform_desc:
                    perform_desc = _safe_str(perf_field.get("text"))
        elif isinstance(perf_field, str) and perf_field:
            perform_desc = perform_desc or perf_field
        if not perform_cpt and perform_desc:
            cpt_match = re.search(r"\(?\bCPT:?\s*(\d{4,5})\b\)?", perform_desc)
            if cpt_match:
                perform_cpt = cpt_match.group(1)
                perform_desc = re.sub(r"\s*\(?\bCPT:?\s*\d{4,5}\b\)?\s*", " ", perform_desc).strip()
        parts = [p for p in (perform_cpt, perform_desc, perform_notes) if p]
        content = " — ".join(parts[:2])
        if perform_notes:
            content = content + "\n" + perform_notes if content else perform_notes

    elif schema_key == "prescribe":
        rx_name = (
            _safe_str(data.get("medication_text"))
            or _get_field_text(data, "fdb_code")
            or _get_field_text(data, "prescribe")
            or _get_field_text(data, "medication")
            or _get_field_text(data, "coding")
            or command_display
        )
        rx_sig = _safe_str(data.get("sig"))
        rx_detail_parts: list[str] = []
        qty = data.get("quantity_to_dispense")
        if qty:
            type_label = _safe_str(data.get("type_to_dispense_label"))
            rx_detail_parts.append(f"Qty: {qty} x {type_label}" if type_label else f"Qty: {qty}")
        days = data.get("days_supply")
        if days:
            rx_detail_parts.append(f"{days}d supply")
        refills = data.get("refills")
        if refills is not None and str(refills) != "":
            suffix = "refills" if int(refills) != 1 else "refill"
            rx_detail_parts.append(f"{refills} {suffix}")
        rx_details = " · ".join(rx_detail_parts)
        rx_pharmacy = _safe_str(data.get("pharmacy_name"))
        rx_pharmacist_note = _safe_str(data.get("note_to_pharmacist"))
        display_parts = [p for p in (rx_name, f"Sig: {rx_sig}" if rx_sig else "", rx_details) if p]
        content = " | ".join(display_parts)

    elif schema_key == "stopMedication":
        stop_name = (
            _safe_str(data.get("medication_text"))
            or _safe_str(data.get("medication_name"))
            or _get_field_text(data, "medication")
            or _get_field_text(data, "coding")
            or command_display
        )
        stop_rationale = _safe_str(data.get("rationale") or data.get("comment") or data.get("narrative"))
        parts = [p for p in (stop_name, stop_rationale) if p]
        content = "\n".join(parts)

    elif schema_key == "removeAllergy":
        remove_name = (
            _safe_str(data.get("allergy_text"))
            or _get_field_text(data, "allergy")
            or _get_field_text(data, "coding")
            or command_display
        )
        remove_rationale = _safe_str(data.get("comment") or data.get("narrative"))
        parts = [p for p in (remove_name, remove_rationale) if p]
        content = "\n".join(parts)

    elif schema_key == "resolveCondition":
        resolve_name = _safe_str(data.get("condition_display")) or _get_field_text(data, "coding") or command_display
        resolve_rationale = _safe_str(data.get("rationale") or data.get("comment") or data.get("narrative"))
        parts = [p for p in (resolve_name, resolve_rationale) if p]
        content = "\n".join(parts)

    elif schema_key in (
        "changeMedication", "adjustPrescription", "refill", "updateDiagnosis",
    ):
        parts = [
            p for p in (
                _get_field_text(data, "coding"),
                _get_field_text(data, "medication"),
                _safe_str(data.get("comment")),
                _safe_str(data.get("narrative")),
            ) if p
        ]
        content = "\n".join(parts)

    elif schema_key == "familyHistory":
        fh_name = _safe_str(data.get("condition_display")) or _get_field_text(data, "family_history")
        relative_val = data.get("relative")
        relative_str = _safe_str(relative_val) if isinstance(relative_val, str) else _get_field_text(data, "relative")
        fh_detail_parts = [p for p in (
            relative_str,
            _safe_str(data.get("note")),
        ) if p]
        fh_details = " · ".join(fh_detail_parts)
        parts = [p for p in (fh_name, fh_details) if p]
        content = "\n".join(parts)

    elif schema_key == "medicalHistory":
        pmh_val = data.get("past_medical_history")
        mh_name = _safe_str(pmh_val) if isinstance(pmh_val, str) else _get_field_text(data, "past_medical_history")
        mh_detail_parts: list[str] = []
        start = _format_date(data.get("approximate_start_date"))
        end = _format_date(data.get("approximate_end_date"))
        if start and end:
            mh_detail_parts.append(f"{start} – {end}")
        elif start:
            mh_detail_parts.append(start)
        mh_comment = _safe_str(data.get("comments") or data.get("comment"))
        if mh_comment:
            mh_detail_parts.append(mh_comment)
        mh_details = " · ".join(mh_detail_parts)
        parts = [p for p in (mh_name, mh_details) if p]
        content = "\n".join(parts)

    elif schema_key == "surgicalHistory":
        sh_name = _safe_str(data.get("procedure_display")) or _get_field_text(data, "past_surgical_history")
        sh_detail_parts = [p for p in (
            _format_date(data.get("approximate_date")),
            _safe_str(data.get("comment")),
        ) if p]
        sh_details = " · ".join(sh_detail_parts)
        parts = [p for p in (sh_name, sh_details) if p]
        content = "\n".join(parts)

    elif schema_key in ("goal", "closeGoal", "updateGoal"):
        content = _safe_str(data.get("goal_statement") or data.get("narrative"))

    elif schema_key == "refer":
        refer_name = _safe_str(data.get("refer_to_display")) or _get_field_text(data, "coding")
        refer_detail_parts = [p for p in (
            _safe_str(data.get("clinical_question")),
            _safe_str(data.get("priority")),
            _safe_str(data.get("notes_to_specialist")),
        ) if p]
        refer_details = " · ".join(refer_detail_parts)
        if not refer_details:
            refer_details = _safe_str(data.get("comment"))
        parts = [p for p in (refer_name, refer_details) if p]
        content = "\n".join(parts)

    elif schema_key == "labOrder":
        lab_partner = _safe_str(data.get("lab_partner_name")) or _get_field_text(data, "coding")
        test_names = data.get("test_names")
        lab_tests = ", ".join(str(t) for t in test_names) if test_names and isinstance(test_names, list) else ""
        lab_order_field = data.get("lab_order")
        if not lab_tests and isinstance(lab_order_field, dict):
            nested_tests = lab_order_field.get("test_names")
            if nested_tests and isinstance(nested_tests, list):
                lab_tests = ", ".join(str(t) for t in nested_tests)
            if not lab_partner:
                lab_partner = _safe_str(lab_order_field.get("lab_partner_name"))
        lab_name = lab_tests or lab_partner or _get_field_text(data, "lab_order") or command_display
        lab_comment = _safe_str(data.get("comment"))
        lab_fasting = bool(data.get("fasting_required"))
        lab_dx_displays = data.get("diagnosis_displays", [])
        if not isinstance(lab_dx_displays, list):
            lab_dx_displays = []
        content_parts: list[str] = []
        if lab_tests:
            content_parts.append(lab_tests)
        if lab_partner:
            content_parts.append(lab_partner)
        if lab_comment:
            content_parts.append(lab_comment)
        if lab_fasting:
            content_parts.append("Fasting")
        content = " | ".join(content_parts) or lab_name

    elif schema_key == "imagingOrder":
        img_name = _safe_str(data.get("image_display")) or _get_field_text(data, "coding")
        img_detail_parts = [p for p in (
            _safe_str(data.get("additional_details")),
            _safe_str(data.get("comment")),
            _safe_str(data.get("priority")),
            _safe_str(data.get("ordering_provider_name")),
            _safe_str(data.get("service_provider_name")),
        ) if p]
        img_details = " · ".join(img_detail_parts)
        parts = [p for p in (img_name, img_details) if p]
        content = "\n".join(parts)

    elif schema_key == "followUp":
        content = _safe_str(data.get("comment") or data.get("narrative"))

    elif schema_key == "task":
        task_name = _safe_str(data.get("title") or data.get("comment"))
        task_detail_parts: list[str] = []
        due = _safe_str(data.get("due_date"))
        if due:
            task_detail_parts.append(f"Due: {_format_date(due)}")
        assignee = data.get("assign_to")
        if assignee and isinstance(assignee, dict):
            assignee_label = _safe_str(assignee.get("label"))
            if assignee_label:
                task_detail_parts.append(assignee_label)
        labels = data.get("labels")
        if labels:
            if isinstance(labels, list):
                task_detail_parts.append(", ".join(str(lbl) for lbl in labels))
            else:
                task_detail_parts.append(str(labels))
        task_comment = _safe_str(data.get("comment"))
        if task_comment and task_comment != task_name:
            task_detail_parts.append(f"Comment: {task_comment}")
        task_details = " · ".join(task_detail_parts)
        parts = [p for p in (task_name, task_details) if p]
        content = "\n".join(parts)

    elif schema_key == "vitals":
        vitals_parts: list[dict[str, str]] = []
        systole = data.get("blood_pressure_systole")
        diastole = data.get("blood_pressure_diastole")
        if systole and diastole:
            vitals_parts.append({"label": "BP", "value": f"{systole}/{diastole}", "unit": "mmHg"})
        hr = data.get("pulse") or data.get("heart_rate")
        if hr:
            vitals_parts.append({"label": "HR", "value": str(hr), "unit": "bpm"})
        rr = data.get("respiration_rate") or data.get("respiratory_rate")
        if rr:
            vitals_parts.append({"label": "RR", "value": str(rr), "unit": "/min"})
        spo2 = data.get("oxygen_saturation") or data.get("pulse_ox")
        if spo2:
            vitals_parts.append({"label": "SpO2", "value": str(spo2), "unit": "%"})
        temp = data.get("body_temperature")
        if temp:
            vitals_parts.append({"label": "Temp", "value": str(temp), "unit": "°F"})
        ht = data.get("height") or data.get("body_height")
        if ht:
            vitals_parts.append({"label": "Height", "value": str(ht), "unit": "in"})
        wt = data.get("weight_lbs") or data.get("body_weight")
        if wt:
            vitals_parts.append({"label": "Weight", "value": str(wt), "unit": "lbs"})
        bp_site = data.get("blood_pressure_position_and_site")
        if bp_site is not None:
            site_label = BP_SITE_LABELS.get(bp_site, str(bp_site))
            vitals_parts.append({"label": "Site", "value": site_label, "unit": ""})
        note_val = data.get("note")
        if note_val:
            vitals_parts.append({"label": "Note", "value": str(note_val), "unit": ""})
        content = ", ".join(
            f"{p['label']} {p['value']} {p['unit']}".strip() for p in vitals_parts
        )

    elif schema_key == "questionnaire":
        q_name = _safe_str(data.get("questionnaire_name"))
        questions = data.get("questions", [])
        q_total = len(questions) if isinstance(questions, list) else 0
        q_answered = 0
        questions_display: list[dict[str, str]] = []
        if isinstance(questions, list):
            for q in questions:
                if not isinstance(q, dict):
                    continue
                responses = q.get("responses", [])
                if not isinstance(responses, list):
                    continue
                q_type = _safe_str(q.get("type"))
                q_label = _safe_str(q.get("label"))
                answer = ""
                if q_type in ("TXT", "TEXT", "INTEGER"):
                    for r in responses:
                        if isinstance(r, dict):
                            val = _safe_str(r.get("value")).strip()
                            if val:
                                answer = val
                                q_answered += 1
                                break
                elif q_type in ("SING", "RADIO"):
                    for r in responses:
                        if isinstance(r, dict) and r.get("selected"):
                            answer = _safe_str(r.get("value")).strip()
                            q_answered += 1
                            break
                elif q_type in ("MULT", "CHECKBOX"):
                    selected = [
                        _safe_str(r.get("value")).strip()
                        for r in responses
                        if isinstance(r, dict) and r.get("selected")
                    ]
                    if selected:
                        answer = ", ".join(selected)
                        q_answered += 1
                else:
                    for r in responses:
                        if isinstance(r, dict):
                            val = _safe_str(r.get("value")).strip()
                            if val:
                                answer = val
                                q_answered += 1
                                break
                            if r.get("selected"):
                                answer = _safe_str(r.get("value")).strip()
                                q_answered += 1
                                break
                if q_label and answer:
                    questions_display.append({"label": q_label, "answer": answer})
        encoded = data.get("content", "")
        if encoded:
            html_content = _decode_b64_html(encoded)
        content = q_name

    elif schema_key in ("reviewOfSystems", "physicalExam",
                         "historyReview", "chartReview", "chartSectionReview",
                         "labReview", "imagingReview", "referralReview",
                         "uncategorizedDocumentReview", "structuredAssessment",
                         "ros", "exam"):
        encoded = data.get("content", "")
        if encoded:
            html_content = _decode_b64_html(encoded)
        if not html_content:
            sections_list = data.get("sections", [])
            if sections_list and isinstance(sections_list, list):
                parts = []
                for sec in sections_list:
                    if isinstance(sec, dict):
                        title = _safe_str(sec.get("title"))
                        text = _safe_str(sec.get("text"))
                        if text:
                            parts.append(f"<strong>{title}:</strong> {text}" if title else text)
                html_content = _sanitize_html("<br>".join(parts))

    elif schema_key in ("immunize", "immunizationStatement", "pocLabTest",
                         "educationalMaterial"):
        parts = [
            p for p in (
                _get_field_text(data, "coding"),
                _get_field_text(data, "statement"),
                _safe_str(data.get("comment")),
                _safe_str(data.get("narrative")),
            ) if p
        ]
        content = "\n".join(parts)

    elif schema_key == "visualExamFinding":
        parts = [
            p for p in (
                _get_field_text(data, "coding"),
                _safe_str(data.get("comment")),
                _safe_str(data.get("narrative")),
            ) if p
        ]
        content = "\n".join(parts)

    else:
        content = _safe_str(
            data.get("narrative")
            or data.get("comment")
            or _get_field_text(data, "coding")
        )

    result: dict[str, Any] = {
        "label": label,
        "content": content,
        "html_content": html_content,
        "schema_key": schema_key,
    }
    if schema_key == "vitals":
        result["vitals_parts"] = vitals_parts
    if schema_key == "allergy":
        result["name"] = name
        result["details"] = details
    if schema_key == "prescribe":
        result["name"] = rx_name
        result["sig"] = rx_sig
        result["details"] = rx_details
        result["pharmacy"] = rx_pharmacy
        result["pharmacist_note"] = rx_pharmacist_note
    if schema_key == "refer":
        result["name"] = refer_name
        result["details"] = refer_details
    if schema_key == "labOrder":
        result["name"] = lab_name
        result["lab_partner"] = lab_partner
        result["comment"] = lab_comment
        result["fasting"] = lab_fasting
        result["diagnosis_displays"] = lab_dx_displays
    if schema_key == "imagingOrder":
        result["name"] = img_name
        result["details"] = img_details
    if schema_key == "task":
        result["name"] = task_name
        result["details"] = task_details
    if schema_key == "perform":
        result["cpt_code"] = perform_cpt
        result["description"] = perform_desc
        result["notes"] = perform_notes
    if schema_key == "familyHistory":
        result["name"] = fh_name
        result["details"] = fh_details
    if schema_key == "medicalHistory":
        result["name"] = mh_name
        result["details"] = mh_details
    if schema_key == "surgicalHistory":
        result["name"] = sh_name
        result["details"] = sh_details
    if schema_key == "diagnose":
        result["icd_code"] = dx_icd_code
        result["icd_display"] = dx_display
        result["assessment_lines"] = dx_assessment_lines
    if schema_key == "assess":
        result["icd_code"] = assess_icd_code
        result["icd_display"] = assess_display
        result["assessment_lines"] = assess_assessment_lines
    if schema_key == "stopMedication":
        result["name"] = stop_name
        result["action"] = "STOP"
        result["rationale"] = stop_rationale
    if schema_key == "removeAllergy":
        result["name"] = remove_name
        result["action"] = "REMOVE"
        result["rationale"] = remove_rationale
    if schema_key == "resolveCondition":
        result["name"] = resolve_name
        result["action"] = "RESOLVE"
        result["rationale"] = resolve_rationale
    if schema_key == "medicationStatement":
        result["name"] = med_name
        result["sig"] = med_sig
    if schema_key == "questionnaire":
        result["questionnaire_name"] = q_name
        result["answered"] = q_answered
        result["total"] = q_total
        result["questions_display"] = questions_display
    return result
