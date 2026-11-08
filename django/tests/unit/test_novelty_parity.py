"""The portal's domain novelty equals common-core's (DEAD-13 parity).

Ran against both implementations before the portal copy was removed; now
``ibgc_scoring.compute_domain_novelty_array`` *is* the common-core function and
this test keeps the behaviour the portal relies on pinned.
"""

from __future__ import annotations

import numpy as np
import pytest

scipy_sparse = pytest.importorskip("scipy.sparse")

from common_core.clustering import scoring as cc_scoring  # noqa: E402
from discovery.services.clustering import ibgc_scoring  # noqa: E402


def _cases():
    rng = np.random.default_rng(7)
    for n_rows, n_cols, density in [
        (1, 3, 0.5),
        (6, 4, 0.0),
        (30, 12, 0.3),
        (120, 40, 0.1),
    ]:
        M = scipy_sparse.random(
            n_rows, n_cols, density=density, format="csr", random_state=rng
        )
        M.data[:] = 1
        paths = [rng.choice(["", "c.0", "c.0", "c.1", "c.2.1"]) for _ in range(n_rows)]
        yield M.astype(np.uint8), paths


@pytest.mark.parametrize("case", list(_cases()), ids=lambda c: f"{c[0].shape}")
def test_domain_novelty_matches_common_core(case):
    M, paths = case
    portal = ibgc_scoring.compute_domain_novelty_array(M, paths)
    shared = cc_scoring.compute_domain_novelty_array(M, paths)
    np.testing.assert_array_equal(portal, shared)
    assert portal.dtype == shared.dtype


def test_length_mismatch_raises_in_both():
    M = scipy_sparse.csr_matrix((2, 2), dtype=np.uint8)
    for fn in (
        ibgc_scoring.compute_domain_novelty_array,
        cc_scoring.compute_domain_novelty_array,
    ):
        with pytest.raises(ValueError):
            fn(M, ["a"])
