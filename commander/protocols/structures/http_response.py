from typing import NamedTuple


class HttpResponse(NamedTuple):
    code: int
    response: str
