"""Derive one cohort's typed assay capability from open GDC metadata.

Three bounded requests (status, one project, one pathless file-facet aggregate)
produce a release-pinned, reason-bearing capability record. Unknown
experimental strategies fail closed: an unmapped provider strategy is an error,
never an implicit negative. Data-category, data-type and workflow signals come
from declared tables, so no capability claim is inferred from a cohort name.
"""

from __future__ import annotations

from collections.abc import Mapping

from cancerjev.domain.capability import (
    AccessLevel,
    CapabilityAvailability,
    CapabilityRecord,
    CaseSampleResolution,
    CohortCapability,
    Modality,
)
from cancerjev.domain.measurements import ScientificSource
from cancerjev.gdc.endpoints import (
    GDC_DATA_MODEL_REFERENCE,
    cohort_project_request,
    files_capability_request,
    status_request,
)
from cancerjev.gdc.parsers import (
    PARSER_VERSION,
    FileFacets,
    parse_file_facets,
    parse_projects,
    parse_status,
    response_warnings,
)
from cancerjev.research.acquisition import (
    AcquisitionTransport,
    response_meta,
    response_operational_source,
)


class CapabilityError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


CASE_LEVEL_LIMITATION = (
    "case-to-aliquot resolution is UNVERIFIED; admitted values stay case-labelled"
)

STRATEGY_MODALITIES: Mapping[str, tuple[Modality, ...]] = {
    "WXS": (Modality.MUTATION_WXS,),
    "WGS": (Modality.MUTATION_WGS, Modality.STRUCTURAL_VARIANT),
    "Targeted Sequencing": (Modality.MUTATION_WXS,),
    "RNA-Seq": (Modality.EXPRESSION_RNASEQ,),
    "miRNA-Seq": (Modality.MIRNA,),
    "ncRNA-Seq": (),
    "Expression Array": (),
    "Methylation Array": (Modality.METHYLATION,),
    "Bisulfite-Seq": (Modality.METHYLATION,),
    "Whole Genome Bisulfite Sequencing": (Modality.METHYLATION,),
    "Genotyping Array": (Modality.CNV,),
    "Reverse Phase Protein Array": (Modality.RPPA,),
    "RPPA": (Modality.RPPA,),
    "10x": (Modality.SCRNA_SNRNA,),
    "scRNA-Seq": (Modality.SCRNA_SNRNA,),
    "snRNA-Seq": (Modality.SCRNA_SNRNA,),
    "Single Cell RNA-Seq": (Modality.SCRNA_SNRNA,),
    "Tissue Slide": (),
    "Diagnostic Slide": (),
    "WGA": (),
    "Hi-C": (),
    "ChIP-Seq": (),
    "ATAC-Seq": (),
    "_missing": (),
}

DATA_CATEGORY_MODALITIES: Mapping[str, tuple[Modality, ...]] = {
    "Clinical": (Modality.CLINICAL, Modality.SURVIVAL),
    "Single Cell Analysis": (Modality.SCRNA_SNRNA,),
    "Somatic Structural Variation": (Modality.STRUCTURAL_VARIANT,),
    "Structural Variation": (Modality.STRUCTURAL_VARIANT,),
}

DATA_TYPE_MODALITIES: Mapping[str, tuple[Modality, ...]] = {
    "Fusion": (Modality.FUSION,),
}

WORKFLOW_MODALITIES: Mapping[str, tuple[Modality, ...]] = {
    "STAR - Counts": (Modality.EXPRESSION_RNASEQ,),
    "HTSeq - Counts": (Modality.EXPRESSION_RNASEQ,),
    "HTSeq - FPKM": (Modality.EXPRESSION_RNASEQ,),
    "HTSeq - FPKM-UQ": (Modality.EXPRESSION_RNASEQ,),
    "Aliquot Ensemble Somatic Variant Merging and Masking":
        (Modality.MUTATION_WXS, Modality.MUTATION_WGS),
    "MuSE Variant Aggregation and Masking": (Modality.MUTATION_WXS, Modality.MUTATION_WGS),
    "MuTect2 Variant Aggregation and Masking": (Modality.MUTATION_WXS, Modality.MUTATION_WGS),
    "SomaticSniper Variant Aggregation and Masking":
        (Modality.MUTATION_WXS, Modality.MUTATION_WGS),
    "VarScan2 Variant Aggregation and Masking": (Modality.MUTATION_WXS, Modality.MUTATION_WGS),
    "Pindel Variant Aggregation and Masking": (Modality.MUTATION_WXS, Modality.MUTATION_WGS),
    "DNAcopy": (Modality.CNV,),
    "ASCAT2": (Modality.CNV,),
    "ASCAT3": (Modality.CNV,),
    "AscatNGS": (Modality.CNV,),
    "ABSOLUTE LiftOver": (Modality.CNV,),
    "GATK4 CNV": (Modality.CNV,),
    "SeSAMe Methylation Beta Estimation": (Modality.METHYLATION,),
    "BCGSC miRNA Profiling": (Modality.MIRNA,),
}

NON_ASSAY_WORKFLOWS = frozenset({"_missing"})

MODALITY_METHODS: Mapping[Modality, tuple[str, tuple[str, ...]]] = {
    Modality.MUTATION_WXS: (
        "complete /ssm_occurrences project scan; distinct released cases per gene",
        (),
    ),
    Modality.MUTATION_WGS: (
        "complete /ssm_occurrences project scan; distinct released cases per gene",
        (),
    ),
    Modality.EXPRESSION_RNASEQ: (
        "case-level log2(UQFPKM+1) summaries and Tukey-tail descriptors",
        (),
    ),
    Modality.CNV: (
        "positive /cnv_occurrences provider categories",
        ("the current CNV lane is admitted only for mutation-count survivors",),
    ),
}

MODALITY_REQUIRED_DATA_TYPES: Mapping[Modality, frozenset[str]] = {
    Modality.MUTATION_WXS: frozenset({"Masked Somatic Mutation"}),
    Modality.MUTATION_WGS: frozenset({"Masked Somatic Mutation"}),
    Modality.EXPRESSION_RNASEQ: frozenset({"Gene Expression Quantification"}),
    Modality.CNV: frozenset({
        "Gene Level Copy Number",
        "Copy Number Segment",
        "Masked Copy Number Segment",
        "Allele-specific Copy Number Segment",
    }),
}


def _fan_out(
    counts: Mapping[str, int],
    table: Mapping[str, tuple[Modality, ...]],
    known_empty: frozenset[str],
    unmapped: list[str],
) -> dict[Modality, set[str]]:
    result: dict[Modality, set[str]] = {modality: set() for modality in Modality}
    for name in counts:
        if name in known_empty:
            continue
        modalities = table.get(name)
        if modalities is None:
            unmapped.append(name)
            continue
        for modality in modalities:
            result[modality].add(name)
    return result


def build_cohort_capability(
    *,
    cohort_id: str,
    project_id: str,
    release: str,
    release_commit: str | None,
    data_categories: tuple[str, ...],
    facets: FileFacets,
    sources: tuple[ScientificSource, ...],
    warnings: tuple[str, ...],
) -> CohortCapability:
    """Deterministic capability derivation from one project record and one facet body."""
    strategy_counts = facets.facet("experimental_strategy")
    unknown_strategies = sorted(set(strategy_counts) - set(STRATEGY_MODALITIES))
    if unknown_strategies:
        raise CapabilityError(
            "UNKNOWN_EXPERIMENTAL_STRATEGY",
            "provider strategies outside the declared mapping: " + ", ".join(unknown_strategies),
        )
    unmapped_workflows: list[str] = []
    strategies_by_modality = _fan_out(strategy_counts, STRATEGY_MODALITIES, frozenset(), [])
    workflows_by_modality = _fan_out(
        facets.facet("analysis.workflow_type"), WORKFLOW_MODALITIES, NON_ASSAY_WORKFLOWS,
        unmapped_workflows,
    )
    data_types_by_modality = _fan_out(
        facets.facet("data_type"), DATA_TYPE_MODALITIES, frozenset(), [],
    )
    category_modalities: set[Modality] = set()
    for category in data_categories:
        for modality in DATA_CATEGORY_MODALITIES.get(category, ()):
            category_modalities.add(modality)

    state_warnings = list(warnings)
    for workflow in sorted(unmapped_workflows):
        state_warnings.append(f"provider workflow type outside the declared mapping: {workflow}")

    records: list[CapabilityRecord] = []
    for modality in sorted(Modality, key=lambda item: item.value):
        strategies = tuple(sorted(strategies_by_modality[modality]))
        data_types = data_types_by_modality[modality]
        source_present = (bool(strategies) or modality in category_modalities
                          or bool(data_types))
        required_types = MODALITY_REQUIRED_DATA_TYPES.get(modality)
        required_present = (required_types is None
                            or bool(required_types & set(facets.facet("data_type"))))
        method = MODALITY_METHODS.get(modality)
        if source_present and required_present and method is not None:
            availability = CapabilityAvailability.AVAILABLE
            mechanism, extra_limitations = method
            reason = None
            limitations = (CASE_LEVEL_LIMITATION, *extra_limitations)
        else:
            availability = CapabilityAvailability.UNAVAILABLE
            mechanism = method[0] if (method is not None and source_present) else None
            if not source_present:
                reason = "SOURCE_NOT_PRESENT"
            elif not required_present:
                reason = "REQUIRED_PROVIDER_DATA_NOT_PRESENT"
            else:
                reason = "NO_VALIDATED_METHOD"
            limitations = (CASE_LEVEL_LIMITATION,) if source_present else ()
        records.append(CapabilityRecord(
            modality=modality,
            availability=availability,
            source_present=source_present,
            mechanism=mechanism,
            experimental_strategies=strategies,
            workflow_types=tuple(sorted(workflows_by_modality[modality])),
            case_sample_resolution=CaseSampleResolution.CASE_LEVEL_ONLY,
            access_level=AccessLevel.OPEN,
            limitations=limitations,
            reason=reason,
        ))
    return CohortCapability(
        cohort_id=cohort_id,
        project_id=project_id,
        release=release,
        release_commit=release_commit,
        parser_version=PARSER_VERSION,
        data_model_ref=GDC_DATA_MODEL_REFERENCE,
        records=tuple(records),
        sources=sources,
        warnings=tuple(state_warnings),
    )


def discover_cohort_capability(
    transport: AcquisitionTransport,
    *,
    project_id: str,
    cohort_id: str | None = None,
) -> CohortCapability:
    """Three bounded open-access requests: status, one project, one file-facet aggregate."""
    status_response = transport.request(status_request())
    status = parse_status(status_response.body, response_meta(status_response, None))
    project_response = transport.request(cohort_project_request(project_id))
    project_meta = response_meta(project_response, status.data_release)
    projects = parse_projects(project_response.body, project_meta)
    if len(projects) != 1 or projects[0].project_id != project_id:
        raise CapabilityError(
            "PROJECT_NOT_FOUND",
            f"project {project_id} did not resolve to exactly one open record",
        )
    facets_response = transport.request(files_capability_request(project_id))
    facets_meta = response_meta(facets_response, status.data_release)
    facets = parse_file_facets(facets_response.body, facets_meta)
    project = projects[0]
    sources = tuple(
        response_operational_source(response, release=status.data_release).source
        for response in (status_response, project_response, facets_response)
    )
    warnings = tuple(
        warning
        for body, meta in (
            (status_response.body, response_meta(status_response, None)),
            (project_response.body, project_meta),
            (facets_response.body, facets_meta),
        )
        for warning in response_warnings(body, meta)
    )
    return build_cohort_capability(
        cohort_id=cohort_id or project_id,
        project_id=project_id,
        release=status.data_release,
        release_commit=status.commit,
        data_categories=tuple(project.data_categories),
        facets=facets,
        sources=sources,
        warnings=warnings,
    )
