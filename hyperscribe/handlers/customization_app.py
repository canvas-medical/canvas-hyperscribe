from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.application import Application
from canvas_sdk.templates import render_to_string

from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants


class CustomizationApp(Application):
    def on_open(self) -> Effect:
        content = render_to_string(
            "templates/customization.html",
            {
                "allCustomizationsURL": Authenticator.presigned_url_no_params(
                    self.secrets[Constants.SECRET_API_SIGNING_KEY],
                    f"{Constants.PLUGIN_API_BASE_ROUTE}/customization/all",
                ),
                "saveCommandPromptURL": Authenticator.presigned_url_no_params(
                    self.secrets[Constants.SECRET_API_SIGNING_KEY],
                    f"{Constants.PLUGIN_API_BASE_ROUTE}/customization/command",
                ),
                "saveUIDefaultTabURL": Authenticator.presigned_url_no_params(
                    self.secrets[Constants.SECRET_API_SIGNING_KEY],
                    f"{Constants.PLUGIN_API_BASE_ROUTE}/customization/ui_default_tab",
                ),
            },
        )

        return LaunchModalEffect(
            content=content,
            target=LaunchModalEffect.TargetType.RIGHT_CHART_PANE,
        ).apply()
