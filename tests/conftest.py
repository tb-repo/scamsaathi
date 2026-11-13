from __future__ import annotations

from collections.abc import Iterator

import pytest

from scamsaathi.tools.intel_db import IntelDB


@pytest.fixture(scope="session")
def intel_db() -> Iterator[IntelDB]:
    db = IntelDB.build()  # in-memory, from data/intel
    yield db
    db.close()
