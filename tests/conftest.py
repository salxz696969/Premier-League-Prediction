import pandas as pd
import pytest

from eplpred import data


@pytest.fixture(scope="session")
def matches() -> pd.DataFrame:
    """A small slice of the real data (three seasons) keeps the tests fast."""
    m = data.load_matches()
    return m[m["season"].between(2017, 2019)].reset_index(drop=True)
