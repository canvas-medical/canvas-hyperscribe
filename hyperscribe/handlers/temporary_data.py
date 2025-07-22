from django.db.models import BigIntegerField, CharField
from django.db.models import Model


# ATTENTION temporary data access to the Charge Description Master view


class ChargeDescriptionMaster(Model):
    class Meta:
        managed = False
        app_label = "canvas_sdk"
        db_table = "canvas_sdk_data_charge_description_master_001"

    id: BigIntegerField = BigIntegerField(primary_key=True)
    cpt_code: CharField = CharField()
    name: CharField = CharField()
    short_name: CharField = CharField()
