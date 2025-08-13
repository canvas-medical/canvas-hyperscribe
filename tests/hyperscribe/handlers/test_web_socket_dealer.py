import json

from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.simple_api.websocket import WebSocketAPI
from canvas_sdk.v1.data.patient import Patient

from hyperscribe.handlers.web_socket_dealer import WebSocketDealer


def test_class():
    tested = WebSocketDealer
    assert issubclass(tested, WebSocketAPI)


def test_authenticate():
    tests = [
        ({"canvas-logged-in-user-id": "theUserId", "canvas-logged-in-user-type": "Staff"}, True),
        ({"canvas-logged-in-user-id": "theUserId", "canvas-logged-in-user-type": "Patient"}, False),
        ({}, False),
    ]
    for headers, expected in tests:
        event = Event(EventRequest(context=json.dumps({"channel_name": "theChannel", "headers": headers})))
        event.target = TargetType(id="targetId", type=Patient)
        secrets = {"APISigningKey": "theApiSigningKey"}
        environment = {"CUSTOMER_IDENTIFIER": "theTestEnv"}
        tested = WebSocketDealer(event, secrets, environment)
        assert tested.authenticate() is expected
