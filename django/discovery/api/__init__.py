"""Discovery Platform API: the Django Ninja router mounted at /api/discovery/.

Endpoints documented in /api/docs are open and rate-limited; UI-only ones are
``include_in_schema=False`` and gated to same-origin browser traffic
(``discovery.security.first_party_gate``). Filtering lives in
``discovery.services.ibgc_filters``; the modules here only shape responses.

Known limitation: ``domain_text`` matches any domain on the iBGC's contig, not
only those inside ``bgc_range`` (TODO(v2-range-overlap) in ibgc_filters).
"""

from discovery.api import assets, filters, ibgcs, query, report
from discovery.api._common import make_router

discovery_router = make_router()
for module in (ibgcs, query, report, filters, assets):
    discovery_router.add_router("", module.router)

__all__ = ["discovery_router"]
