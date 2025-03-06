import json
from functools import reduce
from operator import and_

from canvas_sdk.v1.data.lab import LabPartnerTest
from django.db.models import Q

from hyperscribe.handlers.canvas_science import CanvasScience
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.json_schema import JsonSchema
from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe.handlers.structures.settings import Settings


class SelectorChat:
    @classmethod
    def condition_from(
            cls,
            chatter: LlmBase,
            settings: Settings,
            keywords: list[str],
            icd10s: list[str],
            comment: str,
    ) -> CodedItem:
        result = CodedItem(code="", label="", uuid="")
        # retrieve existing conditions defined in Canvas Science
        if conditions := CanvasScience.search_conditions(settings.science_host, keywords + icd10s):
            # retrieve the correct condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant condition diagnosed for a patient out of a list of conditions.",
                "",
            ]
            user_prompt = [
                'Here is the comment provided by the healthcare provider in regards to the diagnosis:',
                '```text',
                f"keywords: {', '.join(keywords)}",
                " -- ",
                comment,
                '```',
                "",
                'Among the following conditions, identify the most relevant one:',
                '',
                "\n".join(f' * {condition.label} (ICD-10: {Helper.icd10_add_dot(condition.code)})' for condition in conditions),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"ICD10": "the ICD-10 code", "label": "the label"}]),
                '```',
                '',
            ]
            schemas = JsonSchema.get(["selector_condition"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas):
                result = CodedItem(
                    label=response[0]['label'],
                    code=Helper.icd10_strip_dot(response[0]["ICD10"]),
                    uuid="",
                )
        return result

    @classmethod
    def lab_test_from(
            cls,
            chatter: LlmBase,
            settings: Settings,
            lab_partner: str,
            expressions: list[str],
            comment: str,
            conditions: list[str],
    ) -> CodedItem:
        result = CodedItem(code="", label="", uuid="")
        lab_tests = []
        for expression in expressions:
            # expression can have several words: look for records that have all of them, regardless of their order
            keywords = expression.strip().split()
            query = LabPartnerTest.objects.filter(lab_partner__name=lab_partner).filter(reduce(and_, (Q(keywords__icontains=kw) for kw in keywords)))
            for test in query:
                lab_tests.append(test)

        if lab_tests:
            prompt_condition = ""
            if conditions:
                prompt_condition = f"The lab test is intended to the patient's conditions: {', '.join(conditions)}."
            # ask the LLM to pick the most relevant test
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to select the most relevant lab test for a patient out of a list of lab tests.",
                "",
            ]
            user_prompt = [
                'Here is the comment provided by the healthcare provider in regards to the lab test to be ordered for the patient:',
                '```text',
                f"keywords: {', '.join(expressions)}",
                " -- ",
                comment,
                '```',
                "",
                prompt_condition,
                "",
                'Among the following lab tests, select the most relevant one:',
                '',
                "\n".join(f' * {concept.order_name} (code: {concept.order_code})' for concept in lab_tests),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"code": "the lab test code", "label": "the lab test label"}]),
                '```',
                '',
            ]
            schemas = JsonSchema.get(["selector_lab_test"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas):
                result = CodedItem(
                    label=response[0]['label'],
                    code=response[0]["code"],
                    uuid="",
                )
        return result
