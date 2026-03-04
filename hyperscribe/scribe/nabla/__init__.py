from hyperscribe.libraries.constants import Constants
from hyperscribe.scribe.nabla.backend import NablaBackend
from hyperscribe.scribe.registry import register_backend

register_backend(Constants.VENDOR_NABLA, NablaBackend)
