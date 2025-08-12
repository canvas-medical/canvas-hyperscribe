from canvas_sdk.handlers.simple_api.websocket import WebSocketAPI


class WebSocketDealer(WebSocketAPI):
    def authenticate(self) -> bool:
        user = self.websocket.logged_in_user
        return isinstance(user, dict) and (user.get("type") == "Staff")  # no SDK constant for Staff
