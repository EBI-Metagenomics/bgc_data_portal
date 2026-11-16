"""Half-open ``int4range`` values for the inclusive coordinates the TSVs carry."""

from django.db.backends.postgresql.psycopg_any import NumericRange


def int4range(start: int, end_inclusive: int) -> NumericRange:
    """Half-open ``[start, end+1)`` int4range value for Postgres."""
    return NumericRange(lower=int(start), upper=int(end_inclusive) + 1, bounds="[)")
