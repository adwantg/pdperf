from pandas_perf_opt import __version__


def test_version_present():
    assert isinstance(__version__, str) and __version__
