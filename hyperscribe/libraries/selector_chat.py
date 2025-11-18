import json

from canvas_sdk.commands.constants import ServiceProvider

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction import Instruction


class SelectorChat:
    @classmethod
    def condition_from(
        cls,
        instruction: Instruction,
        chatter: LlmBase,
        keywords: list[str],
        icd10s: list[str],
        comment: str,
    ) -> CodedItem:
        result = CodedItem(code="", label="", uuid="")
        # retrieve existing conditions defined in Canvas Science
        if conditions := CanvasScience.search_conditions(keywords + icd10s):
            # retrieve the correct condition
            system_prompt = [
                "Medical context: identify most relevant condition diagnosed for patient from list.",
                "",
            ]
            user_prompt = [
                "Provider diagnosis comment:",
                "```text",
                f"keywords: {', '.join(keywords)}",
                comment,
                "```",
                "",
                "Conditions:",
                "\n".join(
                    f" * {condition.label} (ICD-10: {Helper.icd10_add_dot(condition.code)})" for condition in conditions
                ),
                "",
                "Return the ONE most relevant condition as JSON in Markdown code block:",
                "```json",
                json.dumps([{"ICD10": "ICD-10 code", "label": "label"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_condition"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                result = CodedItem(
                    label=response[0]["label"],
                    code=Helper.icd10_strip_dot(response[0]["ICD10"]),
                    uuid="",
                )
        return result

    @classmethod
    def lab_test_from(
        cls,
        instruction: Instruction,
        chatter: LlmBase,
        cache: LimitedCache,
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
            lab_tests.extend(cache.lab_tests(lab_partner, keywords))

        if lab_tests:
            schemas = JsonSchema.get(["selector_lab_test"])
            prompt_condition = ""
            if conditions:
                prompt_condition = f"The lab test is intended to the patient's conditions: {', '.join(conditions)}."
            # ask the LLM to pick the most relevant test
            system_prompt = [
                "Medical context: select most relevant lab test for patient from list.",
                "",
            ]
            user_prompt = [
                "Provider lab test order comment:",
                "```text",
                f"keywords: {', '.join(expressions)}",
                comment,
                "```",
                "",
                prompt_condition,
                "",
                "Lab tests:",
                "\n".join(f" * {concept.label} (code: {concept.code})" for concept in lab_tests),
                "",
                "Return the ONE most relevant lab test as JSON in Markdown code block:",
                "```json",
                json.dumps(schemas, indent=1),
                "```",
                "",
            ]
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                result = CodedItem(label=response[0]["label"], code=response[0]["code"], uuid="")
        return result

    @classmethod
    def contact_from(
        cls,
        instruction: Instruction,
        chatter: LlmBase,
        free_text_information: str,
        zip_codes: list[str],
    ) -> ServiceProvider:
        result = ServiceProvider(first_name="", last_name="", specialty="", practice_name="")
        if contacts := CanvasScience.search_contacts(free_text_information, zip_codes):
            system_prompt = [
                "Medical context: identify most relevant contact for specialist search from list.",
                "",
            ]
            user_prompt = [
                "Provider specialist search comment:",
                "```text",
                free_text_information,
                "```",
                "",
                "Contacts:",
                "\n".join(f" * {cls.summary_of(contact)} (index: {idx})" for idx, contact in enumerate(contacts)),
                "",
                "Return the ONE most relevant contact as JSON in Markdown code block:",
                "```json",
                json.dumps([{"index": "index as integer", "contact": "contact information"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_contact"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                if 0 <= (idx := response[0]["index"]) < len(contacts):
                    result = contacts[idx]

        if not result.first_name:
            result.first_name = "TBD"
        if not result.specialty:
            result.specialty = "TBD"

        return result

    @classmethod
    def summary_of(cls, service_provider: ServiceProvider) -> str:
        result = []
        if service_provider.first_name:
            result.append(service_provider.first_name)

        if service_provider.last_name:
            result.append(service_provider.last_name)

        if service_provider.specialty:
            specialty = service_provider.specialty
            if result:
                result.append("/")
            result.append(specialty)

        if service_provider.business_address:
            address = service_provider.business_address
            if result:
                address = f"({address})"
            result.append(address)

        return " ".join(result)
