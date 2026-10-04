class ScribeError(Exception):
    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


class ScribeAuthError(ScribeError): ...


class ScribeTranscriptionError(ScribeError): ...


class ScribeNoteGenerationError(ScribeError): ...


class ScribeNormalizationError(ScribeError): ...
