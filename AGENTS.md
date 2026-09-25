# OntoJev

OntoJev is an autonomous computational cancer target-discovery system.

## Core rules

```text
GDC evidence
→ strict parsing
→ validated deterministic genomics
→ typed evidence
→ Jev
```

- Jev judges.
- Python decides and executes.
- LLM hypotheses are not evidence.
- Never infer missing = negative.
- Never send raw genomics to Jev.
- Prefer established GDC/GDAN/TCGA/NCI methods over ad hoc methods.
- Core scientific code must be cancer-agnostic.
- LUAD is a campaign profile, not the architecture.
- Researcher runs cannot influence autonomous state at runtime.
- No generic agent framework, DAG engine, microservices or LLM-generated GDC queries.
- Skip tests unless the user asks for them.

## Sources

For GDC work, inspect current upstream sources first:

- https://github.com/NCI-GDC/gdc-docs
- https://github.com/NCI-GDC/gdcdatamodel2
- https://github.com/NCI-GDC/gdc-workflow-overview
- relevant NCI-GDC tool/workflow repositories

Use `gdcdatamodel2` as the GDC data-model authority.

Clone upstream references into an untracked `.upstream/` workspace and record exact SHAs.

## Before changing code

1. Record current HEAD.
2. Inspect the current implementation independently.
3. Verify prompt assumptions against code and upstream sources.
4. Rewrite the implementation plan if the prompt is stale.
5. Make one bounded scientific change.
6. Prefer fixture/replay verification before live dependencies.
7. Keep current, planned and target behavior distinct.

Mutable schema/action/version facts belong in code, not here.
