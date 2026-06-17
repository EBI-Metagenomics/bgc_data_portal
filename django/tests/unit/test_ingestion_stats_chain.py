"""Unit tests for the chained DiscoveryStats refresh after ingestion commands.

Each ingestion/loading command (``load_discovery_data``,
``build_integrated_bgcs``, ``import_clustering_results``) enqueues a
platform-overview ``DiscoveryStats`` refresh once the load succeeds, opt-out via
``--skip-discovery-stats``. With django-tasks there is no Celery ``link=``: the
predecessor task enqueues the stats refresh itself on success (a ``then_*``
flag), so for the async paths these tests assert the flag is passed; for sync
paths they assert the direct enqueue. No DB or worker needed — tasks are mocked.
"""

from __future__ import annotations

from unittest import mock

from django.core.management import call_command

CMD = "discovery.management.commands"


# ── load_discovery_data ──────────────────────────────────────────────────────


def _run_load(**opts):
    """Invoke load_discovery_data with run_pipeline + tasks patched out."""
    with (
        mock.patch(f"{CMD}.load_discovery_data.run_pipeline") as run_pipeline,
        mock.patch("discovery.tasks.update_protein_search_index_task") as protein,
        mock.patch("discovery.tasks.update_discovery_stats_task") as stats,
    ):
        call_command("load_discovery_data", data_dir="/tmp/x", **opts)
        run_pipeline.assert_called_once()
        return protein, stats


def test_load_chains_stats_onto_protein_index_by_default():
    protein, stats = _run_load()
    # Stats is chained by the protein-index task itself (then_update_stats=True).
    protein.enqueue.assert_called_once()
    assert protein.enqueue.call_args.kwargs["then_update_stats"] is True
    # The command no longer enqueues stats directly in this path.
    stats.enqueue.assert_not_called()


def test_load_skip_discovery_stats_leaves_chain_off():
    protein, stats = _run_load(skip_discovery_stats=True)
    protein.enqueue.assert_called_once()
    assert protein.enqueue.call_args.kwargs["then_update_stats"] is False
    stats.enqueue.assert_not_called()


def test_load_skip_protein_index_dispatches_stats_directly():
    protein, stats = _run_load(skip_protein_index=True)
    protein.enqueue.assert_not_called()
    stats.enqueue.assert_called_once_with()


def test_load_skip_both_dispatches_nothing():
    protein, stats = _run_load(skip_protein_index=True, skip_discovery_stats=True)
    protein.enqueue.assert_not_called()
    stats.enqueue.assert_not_called()


# ── build_integrated_bgcs ────────────────────────────────────────────────────


def _run_build(**opts):
    with (
        mock.patch(f"{CMD}.build_integrated_bgcs.build_integrated_bgcs_task") as build,
        mock.patch(f"{CMD}.build_integrated_bgcs.update_discovery_stats_task") as stats,
    ):
        call_command("build_integrated_bgcs", **opts)
        return build, stats


def test_build_async_chains_stats_on_parent_queue():
    build, stats = _run_build(queue="scores")
    build.using.assert_called_once_with(queue_name="scores")
    enqueue = build.using.return_value.enqueue
    enqueue.assert_called_once_with(then_update_stats=True, stats_queue="scores")


def test_build_async_skip_discovery_stats():
    build, stats = _run_build(skip_discovery_stats=True)
    enqueue = build.using.return_value.enqueue
    enqueue.assert_called_once_with(then_update_stats=False, stats_queue="scores")


def test_build_sync_dispatches_stats_after_success():
    build, stats = _run_build(sync=True, queue="scores")
    build.call.assert_called_once()
    stats.using.assert_called_once_with(queue_name="scores")
    stats.using.return_value.enqueue.assert_called_once_with()


def test_build_sync_skip_discovery_stats():
    build, stats = _run_build(sync=True, skip_discovery_stats=True)
    stats.using.assert_not_called()


# ── import_clustering_results ────────────────────────────────────────────────

_PAYLOAD = {
    "run": {"sha256": "a" * 64, "device": "cpu", "n_levels": 2},
    "hierarchy": {"ibgc_id": []},
    "partial_assignments": {"ibgc_id": []},
    "gcf_nodes": {"family_path": []},
}


def _run_import(tmp_path, **opts):
    tarball = tmp_path / "out.tgz"
    tarball.write_bytes(b"x")
    with (
        mock.patch(
            "common_core.clustering.io.read_outputs_tarball", return_value=_PAYLOAD
        ),
        mock.patch(
            f"{CMD}.import_clustering_results.Command._apply",
            return_value=mock.Mock(pk=7),
        ) as apply,
        mock.patch("discovery.tasks.update_discovery_stats_task") as stats,
    ):
        call_command("import_clustering_results", str(tarball), **opts)
        return apply, stats


def test_import_dispatches_stats_after_success(tmp_path):
    apply, stats = _run_import(tmp_path)
    apply.assert_called_once()
    stats.using.assert_called_once_with(queue_name="scores")
    stats.using.return_value.enqueue.assert_called_once_with()


def test_import_dry_run_skips_stats(tmp_path):
    apply, stats = _run_import(tmp_path, dry_run=True)
    apply.assert_not_called()
    stats.using.assert_not_called()


def test_import_skip_discovery_stats(tmp_path):
    apply, stats = _run_import(tmp_path, skip_discovery_stats=True)
    apply.assert_called_once()
    stats.using.assert_not_called()
