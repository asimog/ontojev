"""Shared test helpers: canned demo workspaces and canned capability fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

from cancerjev.config import Settings
from cancerjev.domain.capability import CohortCapability
from cancerjev.gdc.parsers import FileFacets
from cancerjev.research.capability import build_cohort_capability
from cancerjev.research.orchestrator import DemoOrchestrator
from cancerjev.storage.artifacts import ArtifactStore
from cancerjev.storage.database import Database
from cancerjev.storage.repositories import Repository

CANNED_SETTINGS = (0, 60, "http://localhost:3000")


def build_canned_demo(data_dir: Path) -> str:
    """Bootstrap a repository with one canned demo run and checkpoint the WAL."""
    settings = Settings(data_dir, *CANNED_SETTINGS)
    database = Database(settings.database_path)
    database.bootstrap()
    repository = Repository(database)
    try:
        return DemoOrchestrator(settings, repository, ArtifactStore(data_dir),
                                lambda event: None).run()
    finally:
        with database.connect(write=True) as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def copy_canned_demo(source: Path, target: Path) -> tuple[Settings, Repository, ArtifactStore]:
    """Copy a checkpointed canned demo workspace and open it per-test."""
    shutil.copytree(source, target)
    settings = Settings(target, *CANNED_SETTINGS)
    return settings, Repository(Database(settings.database_path)), ArtifactStore(target)


def canned_capability(*, complete: bool = True) -> CohortCapability:
    """Facet aggregate covering every enabled LUAD modality, or mutation only."""
    if complete:
        facets = FileFacets(
            total_open_files=15,
            counts={
                "experimental_strategy": {"WXS": 5, "RNA-Seq": 5, "Genotyping Array": 5},
                "analysis.workflow_type": {
                    "Aliquot Ensemble Somatic Variant Merging and Masking": 5,
                    "STAR - Counts": 5, "ASCAT2": 5},
                "data_type": {"Masked Somatic Mutation": 5, "Gene Expression Quantification": 5,
                              "Gene Level Copy Number": 5},
            },
            warnings=[],
        )
    else:
        facets = FileFacets(
            total_open_files=5,
            counts={
                "experimental_strategy": {"WXS": 5},
                "analysis.workflow_type": {"Aliquot Ensemble Somatic Variant Merging and Masking": 5},
                "data_type": {"Masked Somatic Mutation": 5},
            },
            warnings=[],
        )
    return build_cohort_capability(
        cohort_id="TCGA-LUAD", project_id="TCGA-LUAD", release="Data Release TEST",
        release_commit="0" * 40, data_categories=("Clinical",), facets=facets,
        sources=(), warnings=())


def fake_release_observation(*, release: str = "Data Release TEST",
                             commit: str | None = "0" * 40):
    """A typed release observation that never touches a provider."""
    from cancerjev.domain.measurements import Acquisition, ScientificSource
    from cancerjev.research.release_monitor import ReleaseObservation

    source = ScientificSource(
        endpoint="/status", request_hash="a" * 64, response_hash="b" * 64,
        parser_version="gdc-parser-v1", release=release, acquisition=Acquisition.COMPLETE)
    return ReleaseObservation(release=release, release_commit=commit, source=source)
