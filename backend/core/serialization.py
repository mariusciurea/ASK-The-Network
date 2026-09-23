"""Make database rows safe to hand back to the model.

A tool result travels into the next LLM request as JSON. The MySQL driver,
however, returns types that `json.dumps` cannot encode:

* `SUM(...)`, `AVG(...)` and DECIMAL columns  -> `decimal.Decimal`
* `STR_TO_DATE(...)`, DATETIME columns        -> `datetime.datetime`
* `TIMEDIFF(...)`                             -> `datetime.timedelta`
* BLOB columns                                -> `bytes`

Any of those in a tool result kills the whole agent turn with
`TypeError: Object of type Decimal is not JSON serializable`, so rows are
normalised once, at the boundary where they enter the agent.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any


def json_safe_value(value: Any) -> Any:
    """Convert one database value into something JSON can represent.

    Args:
        value: A value as returned by the database driver.

    Returns:
        The value itself when it is already JSON-friendly, otherwise a
        number or a string carrying the same meaning.
    """

    if isinstance(value, bool) or value is None:
        return value

    if isinstance(value, Decimal):
        # Counts must stay integers: "12" reads better than "12.0" in a report.
        return int(value) if value == value.to_integral_value() else float(value)

    if isinstance(value, (datetime, date, time)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()

    if isinstance(value, timedelta):
        return str(value)

    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")

    if isinstance(value, set):
        return sorted(str(item) for item in value)

    return value


def json_safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise every value of every row.

    Args:
        rows: Rows as returned by SQLAlchemy.

    Returns:
        The same rows with JSON-serialisable values.
    """

    return [{key: json_safe_value(value) for key, value in row.items()} for row in rows]
