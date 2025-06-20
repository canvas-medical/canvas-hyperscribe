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


class LastNoteStateEvent(Model):
    NEW = "NEW"
    PUSHED = "PSH"
    LOCKED = "LKD"
    UNLOCKED = "ULK"
    DELETED = "DLT"
    RELOCKED = "RLK"
    RESTORED = "RST"
    RECALLED = "RCL"
    UNDELETED = "UND"

    class Meta:
        managed = False
        app_label = "canvas_sdk"
        db_table = "canvas_sdk_last_note_state_event_001"

    dbid: BigIntegerField = BigIntegerField(primary_key=True)
    state: CharField = CharField()
    note_id: BigIntegerField = BigIntegerField()

    def editable(self) -> bool:
        return self.state in [self.NEW, self.PUSHED, self.UNLOCKED, self.RESTORED, self.UNDELETED]
