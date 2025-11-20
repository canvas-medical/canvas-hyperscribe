from canvas_sdk.handlers.simple_api.websocket import WebSocketAPI

from hyperscribe.libraries.constants import Constants


class WebSocketDealer(WebSocketAPI):
    def authenticate(self) -> bool:
        user = self.websocket.logged_in_user
        return isinstance(user, dict) and (user.get("type") == Constants.USER_TYPE_STAFF)  # no SDK constant for Staff
