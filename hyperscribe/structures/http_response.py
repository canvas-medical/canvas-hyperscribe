from typing import NamedTuple

from hyperscribe.structures.token_counts import TokenCounts


class HttpResponse(NamedTuple):
    code: int
    response: str
    tokens: TokenCounts
