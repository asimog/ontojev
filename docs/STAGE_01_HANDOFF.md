# Stage 0–1 implementation handoff

2026-09-25. Scope: the user's next implementation unit, **Stage 0 followed by Stage 1 only**.
This is not completion of discovery architecture or scientific validation.

## Baseline and compatibility

Starting and final HEAD: `fb52305b3d42a39b05f6c269bbfa3d6213fd51d2`; branch `main`.
The starting tree was clean. Changes are uncommitted; no push or database/artifact migration.

Baseline: Python 3.14.3, pytest 8.4.2, Ruff 0.16.8, typesafe-sdk 0.7.1, Pydantic 2.12.4.
Ruff passed and the pre-change offline suite returned **380 passed, 2 deselected**, exit 0.
The local verification checker is mypy 2.3.1, installed with its dependencies in ignored `.venv`
(system site packages are visible); the global Python/plugin environment was not changed.
Python 3.12 remains the configured CI target; no fresh remote CI or local 3.12 execution is claimed.

Retained architecture campaign: all **69 bodies / 6,093,958 bytes** match the original ledger.
Ledger SHA-256: `fc5ddcb2d0c4981e500dac5d6b7ed04dd7676c4f6911040d21076784b2fb4225`.
Location/provenance: [capture register](GDC_DISCOVERY_CAPTURES.md). No captures were rewritten or
imported as fixtures. New tests use existing synthetic fixtures/replay and declared synthetic records.
This is an offline integrity recheck, not a new live measurement.

## Exact implementation

| File | Responsibility |
|---|---|
| `cancerjev/domain/measurements.py` | Frozen entity/population/universe/method/source/quality/coverage and observed/unavailable variants; typed ContractError |
| `cancerjev/domain/scientific.py` | Entity-bound mutation/local-expression/CNV records, explicit unavailable lanes, StatisticalStateV3 |
| `cancerjev/domain/evidence.py` | ActionRef, EvidenceCheck, derived CheckSummary, immutable E0/E1/E2 EvidenceStateV3 |
| `cancerjev/domain/_json.py` | Strict JSON boundary primitives, duplicate-key/nonfinite/version rejection |
| `cancerjev/domain/codecs.py` | Direct v3 readers, canonical writers, scientific identity and version dispatch |
| `cancerjev/domain/legacy_codecs.py` | v1/v2 original-byte snapshots and typed historical summaries; no v3 reinterpretation |
| `cancerjev/domain/identity.py` | Reject unsupported/coerced legacy versions; preserve supported identity payloads |
| `cancerjev/research/specs.py` | ResearchSpecV2, concrete universe/lane/limit records and strict composition reader; original production spec unchanged |
| `cancerjev/science/methods.py` | Reject invalid legacy metric values, without changing valid arithmetic/serialization |
| `pyproject.toml`, `.github/workflows/ci.yml` | Mypy development dependency and strict seven-module Python CI check |
| `tests/test_scientific_baseline.py` | Fixed historical state/evidence/projection/question/event goldens |
| `tests/unit/test_scientific_contracts.py` | New contract, identity, round-trip and malformed-boundary tests |
| `tests/unit/test_versioned_readers.py` | Historical readers and E0/E1/E2 replay, failure and event-order tests |

`_json.py` is shared boundary validation, not a generic serialization framework. Legacy and v3 readers
are separate because their units, statuses and representations must not silently converge.
No generic metric bag, reflection-driven decoder, dependency-injection framework or new Repository.

The NGS somatic/variant and bulk-expression/QC guidance influenced entity/population binding,
normalized-value units, explicit missingness and refusal to infer callable negatives or specimen joins.
No pipeline, executable, external scientific database or model was invoked through a skill.
Jev semantics did not change; its existing question definitions are protected by hash goldens.

## Verification record

Focused verification: **144 passed**, including old scientific/spec tests and new contract/readers.
Final offline gate: **494 passed, 2 deselected, 1 warning in 81.06 seconds**, exit 0.
Ruff passed; mypy reported no issues in seven source files. `git diff --check` and separate
new-file whitespace checks passed. All 40 local Markdown link targets in changed documents resolved.
Runtime dependency equality and the untouched frontend/API/GDC/storage/Jev/LLM paths were checked.
**Stages 0 and 1 pass for this standalone contract/readers unit.** Stages 2–9 were not run.

```text
python -m ruff check cancerjev apps/api tests
python -m pytest
.venv/Scripts/python -m mypy
git diff --check
```

The venv prefix only selects the locally installed development checker; CI invokes `python -m mypy`.
Pytest emits an existing pytest-asyncio deprecation and a Windows pytest-current cleanup
PermissionError after successful exit. These were present in the baseline; they are not test failures.
A standalone temporary fixture capture also hit a Windows SQLite cleanup lock after computing its
result; the committed fixture regression test subsequently passed. No production data was used.

Protected goldens (full expectations live in tests):

- v1 state `1695cdd2…`, v1 evidence `f558ac40…`, v2 state `4df87b5c…`.
- Canonical projection byte hash `b93151e6…`; question hashes Wide `e515f2c1…`, Deep `262d5ae4…`,
  hypothesis `77f459d7…`. No new projections/questions/policy thresholds.
- Fixture type/stage stream: 71 events, hash `cdd7da75…`.
- Live synthetic replay preserves E0/E1/E2, check totals 0/5/4, original stored scientific hashes,
  immutable artifact bytes, both existing actions, explicit dispatch order and final dossier.

## Thirty-point implementation checklist

| # | Item | Outcome |
|---|---|---|
| 1 | Starting/final HEAD and branch | Recorded above; unchanged main, no commit/push |
| 2 | Starting worktree | Clean; all current changes belong to this unit |
| 3 | Baseline environment | Recorded above; no scientific toolchain installed |
| 4 | Baseline offline gate | 380 passed, Ruff passed; known warnings retained |
| 5 | Prior capture preservation | 69 original hashes/lengths match; no new campaign |
| 6 | Stage 0 regression evidence | Fixed identities, projection/questions and fixture/live event ordering |
| 7 | Measurement variants | Non-null observed values; strict non-bool counts; finite scalars; unavailable has reason/no value |
| 8 | Common context | Entity, population, universe, method, source and operational records implemented |
| 9 | Population/coverage | Membership, disjoint valid/missing accounting and summary minimum n checked |
| 10 | Quality/missingness | Acquisition, sufficiency and compatibility remain separate; explicit disabled/unacquired lanes |
| 11 | Mutation contract | Entity/frame-bound counts, no wild-type or callable-denominator inference |
| 12 | Expression contract | Local normalized-value summary contract; not DE; provider summaries retained in legacy bytes |
| 13 | CNV contract | Raw positive occurrence context only; runtime/parser/descriptors remain gated Stage 6 |
| 14 | StatisticalStateV3 | Frozen composed lane records and separately linked operational sources |
| 15 | EvidenceStateV3 | Accepted hash, parent/action requirements, E0/E1/E2 caps and checked summary |
| 16 | ResearchSpecV2 | Small concrete composition; no production profile or CLI switch added |
| 17 | Version dispatch | Explicit 1/2/3 scientific readers; invalid/unknown versions fail, no fixture fallback |
| 18 | Legacy compatibility | Original bytes and valid hashes retained; never relabelled v3 |
| 19 | Identity | Method/value/universe changes affect v3 hash; operational ID/time/cache changes do not |
| 20 | Storage compatibility | Schema 4/writers unchanged; path/size/hash/row binding is Stage 2, not claimed complete |
| 21 | Existing metric defect | Observed-null/bool/invalid count construction rejected; valid baseline hashes unchanged |
| 22 | New demonstrated limitation | Entirely absent expression availability still fails closed in legacy builder; Stage 3 owns correction |
| 23 | Static checking | Strict seven-file mypy scope and Python CI invocation; no blanket ignores |
| 24 | New offline tests | Numeric/schema/immutability/context/revision/identity/legacy replay adversarial cases |
| 25 | Scientific provider budget | Zero new GDC attempts/bytes; zero paid Jev/LLM calls; no cost estimate masquerading as measurement |
| 26 | Scope exclusions | No frontend/API/storage runtime, global plugin, scientific dependency or namespace changes |
| 27 | Documentation | Status, roadmap, domain, architecture, persistence, invariants, testing and this handoff reconciled |
| 28 | Stage 1 boundary | PASS for standalone contracts/readers, not trusted hydration everywhere or discovery readiness |
| 29 | Next implementation gate | Stage 2 artifact/binding/dossier/cache/hypothesis consumption; then Stage 3 typed composition |
| 30 | Later scientific stop | Stage 8 remains BLOCKED ON LABELLED PROSPECTIVE CORPUS; no value claim; Stage 9 inference deferred |

## Ordered continuation and unresolved limitations

1. Stage 2: named storage readers must validate confined paths, byte sizes/hashes and row/artifact
   entity/state/candidate/parent bindings before policy or publication. Refuse publication if the
   authoritative latest revision is corrupt; do not silently choose an earlier one. Validate cached
   answers without paid replacement calls; reject malformed hypothesis drafts/unknown actions.
2. Stage 3: compute and consume typed lanes without internal dictionary reconstruction; preserve
   legacy arithmetic/hash/event goldens. Add typed provider-summary context when that consumer moves,
   and fix the absent-expression-availability composition failure without assigning zero. No new lane
   is safe to activate before this gate.
3. Stages 4–7: separately bounded provider probes/immutable public fixtures before enumeration/CNV
   admission; frozen mutation universe/reduction, explicit independent 100-gene expression arm,
   positive survivor CNV, held-data actions and versioned projections. No paid acceptance calls.
4. Cutover only after all preceding gates; retain historical readers, remove obsolete execution
   branches, keep mutation-required Wide admission. No frontend rendering acceptance is implied.
5. Stage 8 requires qualified blinded labels and a locked prospective corpus. Engineering success
   cannot establish Jev incremental value. Associations, survival, tumor-normal DE, specimen joins,
   causal/clinical/therapeutic claims remain deferred.

New codec validation establishes structural consistency, not source authenticity or the truth of a
supplied number. It does not reexecute deterministic methods, perform cross-artifact resolution or
validate cache/hypothesis policy inputs. Existing production type erosion and dossier/cache gaps
therefore remain explicit, rather than being hidden by the presence of new classes.
