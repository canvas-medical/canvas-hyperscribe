from typing import Type

from django.db.models import BigIntegerField, CharField, ForeignKey, DO_NOTHING
from django.db.models import Model


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


class TemporaryData:

    @classmethod
    def access_to_lab_data(cls) -> bool:
        return cls.model_exists(DataLabView) and cls.model_exists(DataLabTestView)

    @classmethod
    def model_exists(cls, model: Type[Model]) -> bool:
        try:
            model.objects.count()
            return True
        except:
            return False
