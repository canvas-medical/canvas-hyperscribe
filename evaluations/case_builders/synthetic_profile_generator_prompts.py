from __future__ import annotations
import json
from typing import Any


class SyntheticProfileGeneratorPrompts:
    @classmethod
    def med_management_prompts(
        cls, batch_num: int, count: int, schema: dict[str, Any], seen_scenarios: list[str]
    ) -> tuple[list[str], list[str]]:
        system_prompt: list[str] = [
            "You are a clinical-informatics expert generating synthetic patient "
            "profiles for testing medication-management AI systems.",
            "Return your answer as JSON inside a fenced ```json ... ``` block.",
            "The response **must** conform to the following JSON Schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
        ]

        user_prompt = [
            f"Create a JSON object with {count} key-value pairs labeled "
            f'"Patient {1 + (batch_num - 1) * count}" through "Patient {batch_num * count}". '
            "Each value must be a 3-to-5-sentence medication-history narrative "
            "written for a broad audience (≈ 40-60 plain-English words).",
            "",
            "Include **at least two** LOW-complexity patients "
            "(single renewal, first-time Rx, or simple dose tweak). Other patients may be moderate "
            "or high complexity, guided by the diversity checklist below:",
            "- Age bands: <18, 18-30, 30-50, 50-70, >70.",
            "- Social context: homelessness, language barrier, uninsured, rural isolation, etc.",
            "- Novel drug classes: GLP-1 agonists, oral TKIs, depot antipsychotics, inhaled steroids, biologics, "
            "antivirals, contraception, chemo, herbals.",
            "- Edge-case themes: pregnancy, QT risk, REMS, dialysis, polypharmacy/deprescribing, travel medicine, etc.",
            "",
            f"Already-seen motifs: {', '.join(seen_scenarios) if seen_scenarios else 'None yet'}. "
            "**Avoid** re-using templates like ACE-inhibitor-to-ARB cough, long-term warfarin INR drift, "
            "or COPD tiotropium boilerplate.",
            "",
            "Write in clear prose with minimal jargon. If a medical abbreviation is unavoidable, "
            "spell it out the first time (e.g., 'twice-daily (BID)'). Prefer full words: 'by mouth' "
            "over 'PO', 'under the skin' over 'SC'. Vary openings: lead with social detail, "
            "medication list, or family history.",
            "",
            "Each narrative MUST include:",
            "• Current medicines in plain words, with some cases not having complete details.",
            "• A scenario involving medication management—straightforward new prescriptions, simple dose "
            "adjustments, or complex edge cases involving risky medications, polypharmacy, or social barriers.",
            "• Any key allergy, condition, or social barrier.",
            "",
            "Do NOT write SOAP notes, vital signs, or assessments.",
            "",
            "Wrap the JSON in a fenced ```json block and output nothing else.",
        ]

        return system_prompt, user_prompt

    @classmethod
    def primary_care_prompts(
        cls, batch_num: int, count: int, schema: dict[str, Any], seen_scenarios: list[str]
    ) -> tuple[list[str], list[str]]:
        system_prompt: list[str] = [
            "You are a clinical-informatics expert generating synthetic patient "
            "profiles for testing primary care AI systems.",
            "Return your answer as JSON inside a fenced ```json ... ``` block.",
            "The response **must** conform to the following JSON Schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
        ]

        user_prompt = [
            f"Create a JSON object with {count} key-value pairs labeled "
            f'"Patient {1 + (batch_num - 1) * count}" through "Patient {batch_num * count}". '
            "Each value must be a 3-to-5-sentence primary care narrative "
            "written for a broad audience (≈ 40-60 plain-English words).",
            "",
            "Include **at least two** LOW-complexity patients "
            "(routine checkup, simple screening, or basic health maintenance). Other patients may be moderate "
            "or high complexity, guided by the diversity checklist below:",
            "- Age bands: <18, 18-30, 30-50, 50-70, >70.",
            "- Social context: homelessness, language barrier, uninsured, rural isolation, etc.",
            "- Common primary care themes: preventive care, chronic disease management, health screenings, "
            "vaccinations, lifestyle counseling, minor acute illnesses, referrals to specialists.",
            "- Health maintenance: annual physicals, mammograms, colonoscopies, blood pressure checks, "
            "diabetes monitoring, cholesterol screening, mental health screening, etc.",
            "",
            f"Already-seen motifs: {', '.join(seen_scenarios) if seen_scenarios else 'None yet'}. "
            "**Avoid** re-using templates like routine diabetes follow-up, hypertension medication adjustment, "
            "or standard annual physical boilerplate.",
            "",
            "Write in clear prose with minimal jargon. If a medical abbreviation is unavoidable, "
            "spell it out the first time (e.g., 'blood pressure (BP)'). Prefer full words and clear language. "
            "Vary openings: lead with chief complaint, preventive care needs, or social context.",
            "",
            "Each narrative MUST include:",
            "• Current health status and any ongoing conditions in plain words.",
            "• A primary care scenario—preventive care, chronic disease management, acute illness, "
            "health screening, or care coordination needs.",
            "• Any relevant social determinants of health, family history, or access barriers.",
            "",
            "Do NOT write SOAP notes, vital signs, or detailed assessments.",
            "",
            "Wrap the JSON in a fenced ```json block and output nothing else.",
        ]

        return system_prompt, user_prompt

    @classmethod
    def serious_mental_illness_prompts(
        cls, batch_num: int, count: int, schema: dict[str, Any], seen_scenarios: list[str]
    ) -> tuple[list[str], list[str]]:
        system_prompt: list[str] = [
            "You are a clinical-informatics expert generating synthetic patient "
            "profiles for testing serious mental illness care coordination AI systems.",
            "Return your answer as JSON inside a fenced ```json ... ``` block.",
            "The response **must** conform to the following JSON Schema:",
            "```json",
            json.dumps(schema, indent=2),
            "```",
        ]

        user_prompt = [
            f"Create a JSON object with {count} key-value pairs labeled "
            f'"Patient {1 + (batch_num - 1) * count}" through "Patient {batch_num * count}". '
            "Each value must be a 3-to-5-sentence serious mental illness care narrative "
            "written for a broad audience (≈ 40-60 plain-English words).",
            "",
            "Include **at least two** STABLE patients "
            "(medication adherent, engaged in treatment, good social support). Other patients may have moderate "
            "or high acuity, guided by the diversity checklist below:",
            "- Age bands: 18-25, 25-40, 40-55, 55-70, >70.",
            "- Diagnoses: schizophrenia, bipolar disorder, major depression with psychotic features, "
            "schizoaffective disorder, treatment-resistant depression, substance use with mental illness.",
            "- Social context: homelessness, family conflict, legal issues, unemployment, housing instability, "
            "limited English proficiency, rural access barriers, lack of insurance.",
            "- Treatment themes: medication non-adherence, side effect management, crisis episodes, "
            "care transitions, peer support, therapy engagement, case management needs.",
            "",
            f"Already-seen motifs: {', '.join(seen_scenarios) if seen_scenarios else 'None yet'}. "
            "**Avoid** re-using templates like standard antipsychotic switch, routine mood stabilizer adjustment, "
            "or typical therapy engagement patterns.",
            "",
            "Write in clear prose with minimal jargon. If a mental health term is unavoidable, "
            "explain it simply (e.g., 'psychosis (losing touch with reality)'). Use person-first language. "
            "Vary openings: lead with current functioning, recent changes, or care coordination needs.",
            "",
            "Each narrative MUST include:",
            "• Current mental health status and any psychiatric medications in plain words.",
            "• A care scenario—medication management, crisis intervention, care coordination, "
            "social support needs, or treatment engagement challenges.",
            "• Relevant psychosocial factors, support systems, or barriers to care.",
            "",
            "Do NOT write clinical assessments, MSE findings, or diagnostic criteria.",
            "",
            "Wrap the JSON in a fenced ```json block and output nothing else.",
        ]

        return system_prompt, user_prompt
