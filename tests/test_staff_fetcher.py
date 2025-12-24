"""Basic test scaffolding for staff fetcher."""

import pytest

from ingestor import staff_fetcher


def test_fetch_staff_list_not_implemented():
    with pytest.raises(NotImplementedError):
        staff_fetcher.fetch_staff_list("engineering")
