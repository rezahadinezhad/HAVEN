"""Validate aggregate process/connection budgets without opening a database."""

import pytest
from haven.server import runtime_limits


def test_default_and_eight_process_budgets():
    assert runtime_limits({}) == (4, 16)
    assert runtime_limits({"HAVEN_API_WORKERS": "8"}) == (8, 8)
    assert runtime_limits({"HAVEN_API_WORKERS": "1", "HAVEN_DB_POOL_SIZE": "32"}) == (1, 32)


@pytest.mark.parametrize(
    "values",
    [
        {"HAVEN_API_WORKERS": "0"},
        {"HAVEN_API_WORKERS": "9"},
        {"HAVEN_API_WORKERS": "invalid"},
        {"HAVEN_DB_POOL_SIZE": "-1"},
        {"HAVEN_DB_POOL_SIZE": "33"},
        {"HAVEN_API_WORKERS": "8", "HAVEN_DB_POOL_SIZE": "16"},
    ],
)
def test_invalid_or_oversubscribed_budget_fails_before_start(values):
    with pytest.raises(ValueError, match="64 connections"):
        runtime_limits(values)
