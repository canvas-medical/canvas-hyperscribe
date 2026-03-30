from canvas_sdk.v1.data import Note

try:
    from canvas_sdk.v1.data import ModelExtension

    _HAS_MODEL_EXTENSION = True
except ImportError:

    class ModelExtension:  # type: ignore[no-redef]
        pass

    _HAS_MODEL_EXTENSION = False


class NoteProxy(Note, ModelExtension):
    """Proxy model to link CustomModels to Note via OneToOneField."""

    class Meta:
        proxy = True
        if not _HAS_MODEL_EXTENSION:
            app_label = "v1"
