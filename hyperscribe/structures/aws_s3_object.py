from __future__ import annotations

from datetime import datetime
from typing import NamedTuple


class AwsS3Object(NamedTuple):
    key: str
    size: int
    last_modified: datetime
