import json
from functools import reduce
from operator import and_
from typing import Type

from canvas_sdk.commands.commands.lab_order import LabOrderCommand
from django.db.models import Model, BigIntegerField, CharField, Q, ForeignKey, DO_NOTHING

from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.base import Base


# ATTENTION temporary data access to the Lab and LabTest views defined as
# CREATE OR REPLACE VIEW public.canvas_sdk_data_health_gorilla_lab_001 AS
# SELECT id, name FROM health_gorilla_lab WHERE active=true;
#
# CREATE OR REPLACE VIEW public.canvas_sdk_data_health_gorilla_lab_test_001 AS
# SELECT test.id as id , lab.id as lab_id, test.order_code, test.order_name, test.keywords, test.cpt_code
# FROM health_gorilla_labtest as test join health_gorilla_lab as lab on test.lab_id=lab.id
# WHERE lab.active=true;


class DataLabView(Model):
    class Meta:
        managed = False
        app_label = "canvas_sdk"
        db_table = "canvas_sdk_data_health_gorilla_lab_001"

    id = BigIntegerField(primary_key=True)
    name = CharField()


class DataLabTestView(Model):
    class Meta:
        managed = False
        app_label = "canvas_sdk"
        db_table = "canvas_sdk_data_health_gorilla_lab_test_001"

    id = BigIntegerField(primary_key=True)
    order_code = CharField()
    order_name = CharField()
    keywords = CharField()
    cpt_code = CharField()
    lab = ForeignKey(DataLabView, on_delete=DO_NOTHING, related_name="tests", null=True)


class LabOrder(Base):
    @classmethod
    def model_exists(cls, model: Type[Model]) -> bool:
        try:
            model.objects.count()
            return True
        except:
            return False

    @classmethod
    def schema_key(cls) -> str:
        return "labOrder"

    def command_from_json(self, parameters: dict) -> None | LabOrderCommand:
        result: None | LabOrderCommand = None
        condition_icd10s: list[str] = []
        prompt_condition = ""
        if "conditionIndex" in parameters and isinstance(parameters["conditionIndex"], list):
            len_conditions = len(self.current_conditions())
            targeted_conditions: list = []
            for idx in parameters["conditionIndex"]:
                if isinstance(idx, int) and 0 <= idx < len_conditions:
                    condition = self.current_conditions()[idx]
                    targeted_conditions.append(condition.label)
                    condition_icd10s.append(self.icd10_strip_dot(condition.code))
            prompt_condition = f"The lab test is intended to the patient's conditions: {', '.join(targeted_conditions)}."

        # retrieve the tests based on the keywords
        lab_tests = []
        for expression in parameters["keywords"].split(","):
            # expression can have several words: look for records that have all of them, regardless of their order
            keywords = expression.strip().split()
            # ATTENTION: We need to determine the lab vendor in a smarter, dynamic way
            query = DataLabTestView.objects.filter(lab__name="Generic Lab").filter(reduce(and_, (Q(keywords__icontains=kw) for kw in keywords)))
            for test in query:
                lab_tests.append(test)
        # ask the LLM to pick the most relevant test
        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to identify the most relevant lab test for a patient out of a list of lab tests.",
            "",
        ]
        conversation.user_prompt = [
            'Here is the comment provided by the healthcare provider in regards to the lab test to be ordered for the patient:',
            '```text',
            f"keywords: {parameters['keywords']}",
            " -- ",
            parameters["comment"],
            '```',
            "",
            prompt_condition,
            "",
            'Among the following lab tests, identify the most relevant one:',
            '',
            "\n".join(f' * {concept.order_name} (code: {concept.order_code})' for concept in lab_tests),
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            json.dumps([{"code": "the lab test code", "label": "the lab test label"}]),
            '```',
            '',
        ]
        response = conversation.chat()
        if response.has_error is False and response.content:
            lab_test_code = response.content[0]["code"]
            lab_test = DataLabTestView.objects.get(order_code=lab_test_code)
            result = LabOrderCommand(
                lab_partner=lab_test.lab.name,
                tests_order_codes=[lab_test.order_code],
                ordering_provider_key=self.provider_uuid,
                diagnosis_codes=condition_icd10s,
                fasting_required=parameters["fastingRequired"],
                comment=parameters["comment"][:127],  # <-- no more than 128 characters
                note_uuid=self.note_uuid,
            )

        return result

    def command_parameters(self) -> dict:
        conditions = "/".join([f'{condition.label} (index: {idx})' for idx, condition in enumerate(self.current_conditions())])

        condition_dict = {}
        if conditions:
            condition_dict = {
                "condition": f"comma separated list of any of: {conditions}, or empty",
                "conditionIndex": "list of the indexes of the conditions for which the lab test is ordered, as integers",
            }

        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the lab test to order",
            "fastingRequired": f"mandatory, True or False, as boolean",
            "comment": "rational of the prescription, as free text limited to 128 characters",
        } | condition_dict

    def instruction_description(self) -> str:
        return ("Lab tests ordered, including the directions, if it requires fasting, and the targeted condition. "
                "There can be only one lab order per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return self.model_exists(DataLabView) and self.model_exists(DataLabTestView)
