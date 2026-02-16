"""Tests for the check_rate_limit function (sliding window, thread safety, edge cases)."""

import threading
import time
from unittest.mock import MagicMock

import pytest

from OdooDevMCP.security.security import _rate_limit_state, check_rate_limit


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

class TestCheckRateLimitBasics:

    def test_allows_requests_within_limit(self, mock_env):
        for _ in range(3):
            check_rate_limit(mock_env, "basic", max_calls=3, period=60)

        with pytest.raises(RuntimeError, match="Rate limit exceeded"):
            check_rate_limit(mock_env, "basic", max_calls=3, period=60)

    def test_resets_after_time_period(self, mock_env):
        check_rate_limit(mock_env, "reset", max_calls=1, period=0.05)

        with pytest.raises(RuntimeError):
            check_rate_limit(mock_env, "reset", max_calls=1, period=0.05)

        time.sleep(0.06)
        # Should allow again
        check_rate_limit(mock_env, "reset", max_calls=1, period=0.05)

    def test_sliding_window_behavior(self, mock_env):
        """Calls at the edge of the window should slide out correctly."""
        # First call at t=0
        check_rate_limit(mock_env, "slide", max_calls=2, period=0.1)
        time.sleep(0.03)

        # Second call at t=30ms
        check_rate_limit(mock_env, "slide", max_calls=2, period=0.1)
        time.sleep(0.03)

        # Third call at t=60ms (should fail, first call still in window)
        with pytest.raises(RuntimeError):
            check_rate_limit(mock_env, "slide", max_calls=2, period=0.1)

        time.sleep(0.05)

        # Fourth call at t=110ms (should succeed, first call expired)
        check_rate_limit(mock_env, "slide", max_calls=2, period=0.1)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestCheckRateLimitThreadSafety:

    def test_concurrent_access(self, mock_env):
        """Concurrent threads should respect the limit."""
        results = []
        lock = threading.Lock()

        def make_request():
            try:
                check_rate_limit(mock_env, "thread", max_calls=5, period=60)
                with lock:
                    results.append(True)
            except RuntimeError:
                with lock:
                    results.append(False)

        threads = [threading.Thread(target=make_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(True) == 5
        assert results.count(False) == 5

    def test_no_race_conditions_in_tracking(self, mock_env):
        """All calls should be tracked without loss."""
        def make_calls():
            for _ in range(10):
                try:
                    check_rate_limit(mock_env, "race", max_calls=100, period=60)
                except RuntimeError:
                    pass

        threads = [threading.Thread(target=make_calls) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 100 calls tracked
        assert len(_rate_limit_state["test_db"]["race"]) == 100


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestCheckRateLimitEdgeCases:

    def test_zero_max_calls_rejects_all(self, mock_env):
        with pytest.raises(RuntimeError):
            check_rate_limit(mock_env, "zero", max_calls=0, period=60)

    def test_very_short_period(self, mock_env):
        check_rate_limit(mock_env, "short", max_calls=1, period=0.001)

        with pytest.raises(RuntimeError):
            check_rate_limit(mock_env, "short", max_calls=1, period=0.001)

        time.sleep(0.002)
        check_rate_limit(mock_env, "short", max_calls=1, period=0.001)

    def test_very_long_period(self, mock_env):
        check_rate_limit(mock_env, "long", max_calls=2, period=3600)
        check_rate_limit(mock_env, "long", max_calls=2, period=3600)

        with pytest.raises(RuntimeError):
            check_rate_limit(mock_env, "long", max_calls=2, period=3600)

    def test_per_database_isolation(self):
        """Different database names should have independent limits."""
        env_a = MagicMock()
        env_a.cr.dbname = "db_alpha"

        env_b = MagicMock()
        env_b.cr.dbname = "db_beta"

        check_rate_limit(env_a, "iso", max_calls=1, period=60)

        # env_b should not be affected
        check_rate_limit(env_b, "iso", max_calls=1, period=60)

        # env_a should be exhausted
        with pytest.raises(RuntimeError):
            check_rate_limit(env_a, "iso", max_calls=1, period=60)

    def test_state_cleared_between_tests(self, mock_env):
        """Verify the autouse reset_rate_limit_state fixture works.

        If this test runs after others that fill the state, it should start clean.
        """
        # Should be empty thanks to the fixture
        assert len(_rate_limit_state) == 0
