from hyperscribe.libraries.constants import Constants
from hyperscribe.scribe.backend.registry import register_backend
from hyperscribe.scribe.clients.nabla.backend import NablaBackend

register_backend(Constants.VENDOR_NABLA, NablaBackend)
