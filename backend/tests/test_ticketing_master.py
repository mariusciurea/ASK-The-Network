"""Regression tests for the ticketing_master semantic layer and SQL guard.

These cover the deterministic half of the agent - the part that must not depend
on what the model feels like generating. They need neither a database nor an
API key.

    python -m pytest backend/tests/test_ticketing_master.py
    python backend/tests/test_ticketing_master.py      # same checks, no pytest
"""

import sqlglot

from backend.core.sql_safety import UnsafeSQLError, parse_read_only
from backend.data_models.models import SQLCommandInput
from backend.network_agent.sub_agents.ticketing_master.data_tools import build_metric_query
from backend.network_agent.sub_agents.ticketing_master.semantic_layer import load_semantic_layer
from backend.network_agent.sub_agents.ticketing_master.sql_guard import guard_sql
from backend.network_agent.sub_agents.ticketing_master.tools import (
    _markdown_cell,
    _safe_filename,
    _safe_sheet_name,
)


LAYER = load_semantic_layer()

# Values the guard is told exist in the database, so the tests stay offline.
KNOWN_VALUES = {
    "loc_identifier": {"DZR1Y", "OCWBF"},
    "subject": {"Link Down", "Fiber Cut Detected"},
    "network_element_identifier": {"OXVOWF7"},
    "status": {"Open", "Closed"},
    "response_subject": {"Behoben", "Root cause fixed"},
}

FILTER_COMBINATIONS = [
    {},
    {"loc_identifier": "DZR1Y"},
    {"ticket_type": "INM", "status_group": "active"},
    {"date_from": "2026-03-01", "date_to": "2026-04-01", "priority": "1"},
    {"subject": "Link Down", "network_element_identifier": "OXVOWF7"},
]


def _guard(sql_query: str) -> str:
    return guard_sql(sql_query, layer=LAYER, known_values=KNOWN_VALUES)


# --- semantic layer ---------------------------------------------------------


def test_semantic_layer_is_consistent():
    """Every metric, filter and group points at something that exists."""

    assert LAYER.dataset.table == "ticket_data"
    assert LAYER.metrics, "the metric catalogue must not be empty"

    for name, metric in LAYER.metrics.items():
        assert "{filters}" in metric.sql, f"metric '{name}' has no filter placeholder"
        assert metric.default_limit > 0

    for column in ("loc_identifier", "network_element_identifier", "subject"):
        assert column in LAYER.lookup_columns

    assert LAYER.free_text_columns == {"description", "response_description"}


def test_core_instruction_stays_small_and_complete():
    """The always-on context carries the rules but not the verbose material."""

    core = LAYER.render_core_instruction()

    assert "loc_identifier" in core
    assert "describe_schema" in core
    for metric_name in LAYER.metrics:
        assert metric_name in core

    # metric SQL, enum values and examples are served on demand, not every turn
    assert "GROUP_CONCAT" not in core
    assert "Kein Fehler" not in core
    assert len(core) < 6000, "the standing instruction is growing, check the token budget"


def test_detail_topics_render():
    for topic in ("columns", "values", "groups", "metrics", "examples", "rules", "limitations"):
        assert LAYER.render_topic(topic).strip()

    try:
        LAYER.render_topic("does-not-exist")
    except ValueError as error:
        assert "unknown topic" in str(error)
    else:
        raise AssertionError("an unknown topic must be rejected")


# --- read-only safety -------------------------------------------------------


def test_read_only_queries_are_accepted():
    for sql_query in (
        "SELECT * FROM ticket_data LIMIT 5",
        "SELECT subject, COUNT(*) AS n FROM ticket_data GROUP BY subject LIMIT 10",
        "WITH recent AS (SELECT ticket_number FROM ticket_data) SELECT * FROM recent LIMIT 5",
    ):
        parse_read_only(sql_query)


def test_write_and_stacked_statements_are_rejected():
    for sql_query in (
        "SELECT 1; DROP TABLE ticket_data",
        "DELETE FROM ticket_data",
        "UPDATE ticket_data SET status = 'Closed'",
        "INSERT INTO ticket_data VALUES (1)",
        "TRUNCATE TABLE ticket_data",
        "SHOW TABLES",
        "SELECT SLEEP(10)",
        "SELECT LOAD_FILE('/etc/passwd')",
        "",
    ):
        try:
            parse_read_only(sql_query)
        except UnsafeSQLError:
            continue
        raise AssertionError(f"query should have been rejected: {sql_query!r}")


def test_tool_input_validation_rejects_writes():
    try:
        SQLCommandInput(sql_query="DROP TABLE ticket_data")
    except ValueError:
        return
    raise AssertionError("SQLCommandInput must reject a write statement")


# --- semantic guard ---------------------------------------------------------


def test_valid_queries_are_not_blocked():
    """Guarding must not get in the way of correct queries."""

    for sql_query in (
        "SELECT ticket_number FROM ticket_data WHERE loc_identifier = 'DZR1Y'",
        "SELECT subject, COUNT(*) AS ticket_count FROM ticket_data "
        "WHERE subject LIKE '%Link%' GROUP BY subject ORDER BY ticket_count DESC LIMIT 10",
        "SELECT ticket_number FROM ticket_data WHERE ticket_number LIKE 'Z_INM%' "
        "AND status IN ('Open', 'Closed') LIMIT 5",
        # explicit free-text search for wording that is not a structured value
        "SELECT ticket_number FROM ticket_data WHERE response_description LIKE '%fiber splice%' LIMIT 50",
        # self-join used by the correlation metric
        "SELECT inm.ticket_number FROM ticket_data AS inm JOIN ticket_data AS chg "
        "ON inm.network_element_identifier = chg.network_element_identifier LIMIT 20",
    ):
        _guard(sql_query)


def test_structured_value_in_free_text_is_blocked():
    """The 'Berlin appears in the description too' failure mode."""

    for sql_query in (
        "SELECT * FROM ticket_data WHERE description LIKE '%DZR1Y%'",
        "SELECT * FROM ticket_data WHERE description LIKE '%link down%'",
        "SELECT * FROM ticket_data WHERE response_description = 'Behoben'",
    ):
        try:
            _guard(sql_query)
        except UnsafeSQLError as error:
            assert "instead" in str(error), "the rejection must name the column to use"
            continue
        raise AssertionError(f"query should have been rejected: {sql_query!r}")


def test_invented_columns_and_tables_are_blocked():
    for sql_query in (
        "SELECT solution_date FROM ticket_data LIMIT 5",
        "SELECT * FROM ticket_data WHERE region = 'Berlin' LIMIT 5",
        "SELECT * FROM network_devices LIMIT 5",
    ):
        try:
            _guard(sql_query)
        except UnsafeSQLError:
            continue
        raise AssertionError(f"query should have been rejected: {sql_query!r}")


def test_exact_columns_reject_like():
    try:
        _guard("SELECT * FROM ticket_data WHERE loc_identifier LIKE '%DZR%'")
    except UnsafeSQLError as error:
        assert "lookup_column_values" in str(error)
        return
    raise AssertionError("LIKE on an exact-match column must be rejected")


def test_limit_is_always_enforced():
    guarded = _guard("SELECT ticket_number FROM ticket_data")
    assert "LIMIT" in guarded.upper()

    capped = _guard("SELECT ticket_number FROM ticket_data LIMIT 100000")
    assert "LIMIT 100000" not in capped.upper()


# --- metrics ----------------------------------------------------------------


def test_every_metric_builds_valid_sql():
    """Each metric must survive every filter combination, offline."""

    for metric_name in LAYER.metrics:
        for combination in FILTER_COMBINATIONS:
            supplied = {name: combination.get(name, "") for name in LAYER.filters}
            sql_query, params, applied = build_metric_query(metric_name, supplied, layer=LAYER)

            runnable = sql_query.replace(":row_limit", "100")
            sqlglot.parse_one(runnable, dialect=LAYER.dataset.dialect)

            # the catalogue must obey the same structural rules as generated SQL
            guard_sql(runnable, layer=LAYER, known_values={})

            assert params["row_limit"] > 0
            assert set(applied) <= set(LAYER.filters)


def test_metric_filters_are_bound_not_interpolated():
    sql_query, params, _ = build_metric_query(
        "top_resolutions", {"loc_identifier": "DZR1Y'; DROP TABLE ticket_data --"}, layer=LAYER
    )

    assert "DROP" not in sql_query
    assert params["loc_identifier"] == "DZR1Y'; DROP TABLE ticket_data --"


def test_invalid_metric_arguments_are_refused():
    for metric_name, supplied in (
        ("does_not_exist", {}),
        ("top_resolutions", {"date_from": "01/03/2026"}),
        ("top_resolutions", {"status_group": "half-open"}),
        ("top_resolutions", {"ticket_type": "XXX"}),
    ):
        try:
            build_metric_query(metric_name, supplied, layer=LAYER)
        except ValueError:
            continue
        raise AssertionError(f"'{metric_name}' with {supplied} should have been refused")


# --- presentation helpers ---------------------------------------------------


def test_report_and_export_helpers_are_defensive():
    assert _markdown_cell("a | b") == "a \\| b"
    assert _markdown_cell(None) == "N/A"
    assert _markdown_cell("x" * 200).endswith("...")

    assert _safe_filename("../../etc/passwd", ".xlsx") == "passwd.xlsx"
    assert _safe_filename("..\\..\\windows\\system32", ".xlsx") == "system32.xlsx"
    assert _safe_filename("report", ".xlsx") == "report.xlsx"
    assert _safe_sheet_name("tickets/2026:march") == "tickets_2026_march"
    assert len(_safe_sheet_name("s" * 60)) == 31


if __name__ == "__main__":
    failures = 0
    for name, test in sorted(dict(globals()).items()):
        if not name.startswith("test_") or not callable(test):
            continue
        try:
            test()
            print(f"PASS {name}")
        except Exception as error:  # noqa: BLE001 - a standalone runner reports everything
            failures += 1
            print(f"FAIL {name}: {type(error).__name__}: {error}")
    print(f"\n{failures} failure(s)")
    raise SystemExit(1 if failures else 0)
