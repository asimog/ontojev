# Python-core truth and type-evidence review

Audited HEAD: `42b05d40e6edafec0b8613e7dd154a60a46e4fee` on main, initially clean.
Rechecked 2026-09-24 against the supplied Python audit. No production/test/dependency changes.
The useful [anti-slop philosophy](https://github.com/dmmulroy/anti-slop) is preserving validated type
evidence and clear seams, not translating TypeScript lint preferences or installing tools.

## Assessment

Strong bounded foundation; unsafe to scale its JSON-shaped internal scientific domain unchanged.
This is a focused contract transition, not a cleanup project. Provider parsing, deterministic
ownership, no-pooling, immutability, explicit abstention and scientific/operational identity separation
are CURRENT AND GOOD. Frozen research configuration is good but CURRENT BUT TOO SPECIALIZED for
independent lanes. There is no demonstrated Jev incremental-value result.

## Type-evidence flow

| Stage | Evidence gained/preserved/lost |
|---|---|
| GDC bytes / decoded JSON | JUSTIFIED BOUNDARY REPRESENTATION |
| parsers.py: CaseRecord, GeneRecord, GeneCaseCounts, ExpressionValues | Typed provider evidence gained; dynamic ID maps justified |
| science.methods.ProjectFrame | Typed container, mutation/expression acquisition bundled |
| science.methods.build_statistical_state | Primary DOMAIN TYPE EROSION: returns dict[str, Any] |
| State mutation/expression/populations/quality/provenance | Known scientific sections represented by key conventions |
| research.ranking and jev.projection | Reconstruct values/status with .get/isinstance/fallback maps |
| TypeSafe adapter -> contracts.validate_answers | Strong boundary roster/range/distribution validation, then returns nested dictionaries |
| service -> cache/database -> policy | Validated answer variants not retained; generic row decoding |
| candidate -> deep -> EvidenceState | Dictionary inputs, dictionary observations and revision assembly |
| ActionDefinition -> ActionOutcome | Typed definition; input/check/prerequisite dictionaries weaken result guarantees |
| hypothesis draft -> record | Bounded boundary validation, then dictionary domain record |
| dossier -> persistence/API | JSON output justified, but scientific inputs must be validated first |

## Rechecked findings and priority

| ID | Evidence at baseline | Classification / demonstrated scope | Disposition |
|---|---|---|---|
| Q1 | methods.py:353 build_statistical_state; deep.py evidence builders; domain/states.py contains enums rather than scientific records | DOMAIN TYPE EROSION; architectural risk, not proof current measurements are wrong | BLOCK transition: typed measurements, lanes, state/evidence and check summary |
| Q2 | methods.py:218 metric | Demonstrated helper accepts metric('audit_missing_observed',None,'cases') as OBSERVED with null value/reason | BLOCK contract invariant; no claim current live path produced this measurement |
| Q3 | dossier.py:263 run_dossier_stage catches read/JSON errors into {}; no expected checksum supplied; build_live_dossier:99 uses row presence | Demonstrated fail-open path: an empty revision payload yields OBSERVED deterministic/project sections, project narrative null | BLOCK trusted dossier output: validate/hash inputs, unavailable/refuse on failure |
| Q4 | repositories.py:632 _decode_row; deep.py:383 load_candidate_evidence | Generic json.loads then dictionary identity calculation; missing versioned domain validation | BLOCK scientific hydration; do not redundantly parse trusted internal objects |
| Q5 | identity.py:34 and evidence counterpart | schema 2 branch, otherwise fixture shape; unsupported versions not explicitly rejected here | BLOCK codecs/version dispatch; current projection guards mitigate some routes |
| Q6 | service.py:433 and _cached_evaluation:481 | Cached answers copied without original roster/value revalidation | FIX during typed hydration; corruption/schema-drift risk, not demonstrated live misclassification |
| Q7 | nextmove.py:48 | Missing checks_contradicted becomes 0 | FIX CheckSummary constructor; absent malformed persistence path is a risk, not a measured false-negative finding |
| Q8 | hypotheses.py:214 validate_generated_drafts | Unknown distinguishing_tests silently removed; individual list strings lack text cap | FIX with typed draft parser; current prose overstates strict rejection |
| Q9 | typesafe_adapter.py:93 constructs client without retry policy; installed typesafe-sdk 0.7.1 RetryPolicy defaults 2 retries | Application evaluation/call counters do not equal underlying HTTP attempts; total spend not reserved | BLOCK scaled paid discovery: explicit retry/attempt/token policy |
| Q10 | openrouter.py:76 only nonblank model validation; CLI:185 injects adapter | Concrete adapter implemented; immutable model resolution not enforced by that check | FIX documentation now; pinned identity/resolved-provider contract before reproducibility claims |
| Q11 | .github/workflows/ci.yml Python job | Ruff+pytest, no static type checker | REQUIRED FOR SYSTEMATIC DISCOVERY: scoped type gate with new contracts, no dependency change this pass |
| Q12 | README/status/AGENTS/budgets/questions | STALE DOCUMENTATION: deep, hypotheses, adapter and caps both present and described absent | Corrected current authority; dated histories retained explicitly |
| Q13 | apps/api/routes.py:219 dossier SQL despite Repository.get_dossier | Small storage read leak | FIX naturally, no new repository |
| Q15 | apps/api/routes.py:system | Hard-coded phase=3 and llm=false contradict current capabilities | STALE runtime metadata; fix naturally with explicit capability reporting |
| Q14 | service.EvaluationContext unused; duplicated wide/general evaluation lifecycle | OPTIONAL LATER simplification | Remove unused helper when touched; consolidate lifecycle without changing question versions |

Q2 and Q3 were also exercised in an isolated offline diagnostic, not added as tests. The Q3 diagnostic
constructed the empty payload produced by the read-error branch and observed OBSERVED/null narrative.
It did not corrupt a real artifact or claim corruption had occurred in a historical run.

## Boundary parsing

GDC required types, finite values, duplicate IDs, pagination offsets/totals, unexpected IDs and partial
aggregations are checked early. Existing expression parser accepted the new captures while preserving
omitted genes/cases. Optional wrong-typed fields may become None in _optional(); retain this for
incidental metadata only, not new scientifically meaningful optional fields.

TypeSafe response validation is strong at initial entry; preserve typed variants afterward.
OpenRouter bounds response bytes/completion and validates envelope/drafts, but generated text is never
scientific evidence and strictness gaps remain Q8/Q10. Database JSON needs direct versioned codecs.
Cursor decoding checks envelope keys and child filter binding but not every scalar type/length:
LATER HARDENING for API robustness, no demonstrated scientific corruption. Operational numeric env
caps reject nonfinite/out-of-range values; model-name pinning is a separate issue.

## Dependency seams and test quality

CURRENT AND GOOD: transport_factory, adapter_factory, OpenRouter opener, deterministic replay and
loopback HTTP tests, real temporary SQLite/artifacts, offline outbound-network guard, event/idempotency
and provenance tests. These mostly test behavior and contracts. tests/jev/test_typesafe_adapter.py
replaces typesafe_sdk in sys.modules; a tiny injected client/factory Protocol is preferable when touched.
Existing callbacks/repository/artifact parameters often use Any: type those existing seams, not a DI
framework. Direct clock/UUID calls are operational and excluded from scientific identity; leave them.

Prior supplied audit at this exact SHA: Ruff command `python -m ruff check cancerjev apps/api tests`
passed; `python -m pytest -q` exited0 at 100%, with ignored Windows temp cleanup PermissionError.
Reused as baseline evidence, not claimed freshly rerun by this documentation pass. Additional checks
here: current helper/dossier diagnostic and replay parsing of campaign captures.

## Scientific ownership and KISS

Responsibility risks are methods.py (methods+all lanes+serialization), live.py (all acquisition+policy
routing), deep.py (hydration+construction+execution), actions.py (all action contracts+implementations)
and service.py (duplicate lifecycle paths). Split only at concrete invariants when implementing lanes.
Repository and provider parsers remain coherent despite length. Identity already excludes run/event/
artifact/attempt IDs and clocks, retaining meaningful source hashes/universe/method/population.

JUSTIFIED BOUNDARY REPRESENTATION: external JSON, SQL parameters, decoded rows before codecs,
generic event envelopes, SDK envelopes and serialized dossiers. Dynamic identifier maps are not
domain erosion when their values are typed. REJECT / DO NOT BUILD: universal lane framework,
new ORM/DAO hierarchy, DI framework, agent/workflow engine, microservices, style rewrites,
anti-slop/Oxlint installation, package rename or frontend cleanup.
