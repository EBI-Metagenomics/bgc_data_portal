"""Drop the unused pgvector extension.

The ESM-C embedding tables and vector columns were removed before the
migration squash; the 2026-11-03 audit on exp found the ``vector`` extension
installed but with no vector-typed columns, no hnsw / ivfflat indexes and no
orphan embedding tables. Nothing depends on it, so dropping it is safe; the
database image can then be plain ``postgres``.

``IF EXISTS`` keeps this a no-op on databases that never had the extension
(e.g. a fresh plain-postgres deployment). Not reversed: re-creating it would
require the pgvector build.
"""

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("discovery", "0008_ibgc_is_partial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP EXTENSION IF EXISTS vector;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
