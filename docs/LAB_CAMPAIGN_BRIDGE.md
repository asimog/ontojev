# Laboratory / Campaign convergence

Implemented from executable code starting at `b14bd645d55f2fa9352534f658d5641454ef8d86`.
Existing documentation and `.upstream` were not used to establish implementation status.

## Current execution

`worker --live` and `lab` use the same `run_lab` supervisor. OntoCodex selects one
Python-preflighted offer per Research Run. `ScientificLabCapabilities` adapts the
existing Campaign functions; it does not call the complete systematic Campaign
inside the Research Run and does not duplicate scientific algorithms.

The available operations are mutation discovery, expression discovery, CNV case
shards, complete CNV merge, canonical multimodal StatisticalState composition,
Wide/admission, and one Candidate investigation through deterministic Stage 8.
OntoCodex chooses the eligible operation and Candidate. No researcher Deep flags
are required by this path. Prerequisites determine eligibility, not scientific priority.

Mutation and expression use their canonical result codecs. Composition reuses
`load_resumed_evidence`, `compose_discovery_states`, and `persist_state`. Wide uses
the existing pre-Wide selection, Jev question set, rankings, and Candidate model.
Candidate investigation uses the existing registered actions, Deep, hypothesis
policy and Stage 8 machinery. Existing scientific readiness and evidence maturity
labels remain unchanged: permission to investigate is not claim validation.

## Persistence and boundaries

The portfolio retains artifact identities, not a second scientific-state model.
Typed stage receipts record the question, project, release, specification hash,
input/output artifact identities and hashes, and canonical state/Candidate IDs.
Resumption verifies autonomous ownership, terminal source runs, artifact bytes,
release and scope compatibility, and the existing lane method contracts.

CNV keeps one case partition after its first selected shard. A merge requires
every shard in the partition. Historical mixed partitions are not silently
relabelled or merged. Expression and mutation can be chosen in either order.

Wide binds selected immutable states to its own operational run while preserving
their scientific hashes. A later Candidate run requires a verified binding to
the exact original Wide receipt, Candidate and accepted state. Stage 8 reads the
original Wide rankings; researcher-owned runs cannot supply autonomous evidence.

The supervisor retains the normal 600-second ceiling and finalization reserve.
Acquisition uses the existing open-access GDC transport, deadline checks, request
and byte ceilings, and ephemeral response store. Successful acquisitions verify
derived evidence and reacquisition provenance before raw cleanup. Budget
exhaustion never produces a smaller population labelled complete.

The restricted director remains Codex CLI -> OpenRouter with the existing
DeepSeek default. Research-control Jev remains shadow. Scientific Wide/Deep Jev
uses the canonical scientific contracts. Model interpretations remain separate
from numerical measurements.

The Laboratory Observatory presents selected capability/modality/budget and stage
output summaries, with full immutable receipts available in the run notebook.

## Deployment

The Docker image installs a pinned upstream Codex CLI with Node and git and runs
`codex --version` during the image build. Installation follows the
[official Codex CLI documentation](https://learn.chatgpt.com/docs/codex/cli).
The deployed `worker --live` enters the lab supervisor, rather than the old
Program scheduler. Persist the configured `CANCERJEV_DATA_DIR` volume; raw shard
workspaces are disposable. Provider credentials remain runtime configuration.

The legacy explicit Program/Campaign commands remain diagnostic execution paths;
their readiness gates have not been deleted or promoted. They are no longer the
deployment worker's autonomous scheduler.

## Verified scope and remaining work

The integrated offline replay reconstructs stores/executors between successive
runs and proves question -> expression/mutation -> multiple ephemeral CNV shards
-> merge -> StatisticalState -> Wide -> canonical Candidate -> Deep -> Stage 8
dossier -> another question. It also checks immutable prior states and rejects
corrupt resumed lane artifacts. Offline replay is not live scientific validation.

This is a convergence milestone, not completion of every requested capability:

- Mutation/expression adapters currently attempt an entire canonical lane within
  the declared budget. They do not yet checkpoint individual occurrence pages or
  expression batches. A large real cohort can therefore exhaust the allowance
  without advancing that lane; this limitation is included in director offers.
- The Candidate arc remains one bounded operation, not separately selectable
  Deep, hypothesis and follow-up run units. Existing hypothesis generation stays
  unavailable without a configured generator; no synthetic fallback is added.
- The capability-gap engineering worktree/verification/activation loop is not
  implemented. CAPABILITY_GAP remains durable research control state. Installing
  git in the image does not constitute engineering autonomy.
- Replication and additional registered methods still need individual bounded
  adapters. Existing historical Program records are not migrated into LabState.
- Restart between completed blocks is replay-tested. Recovery of every possible
  interruption between scientific publication and portfolio publication needs
  further fault-injection work before unattended production claims.

Next implementation units should address these limits before enabling claims of
complete autonomous deployment or long-running live Campaign coverage.
