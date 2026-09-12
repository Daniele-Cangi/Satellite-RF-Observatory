# Development and integration workflow

Main contains completed, tested work, including research prototypes whose
scientific limitations remain explicit. Integration does not change an
experiment's outcome or turn a synthetic result into RF qualification.

1. Start scoped implementation from the current main branch. Preserve old
   scientific sources, plans and results; extend through separately versioned
   modules and immutable reports where source hashes are already recorded.
2. Run checks appropriate to the change and inspect the full outgoing diff.
   Verify historical source manifests when scientific modules are involved.
3. Push the working branch and open a pull request describing the resulting
   behavior, evidence, failures and remaining limitations. Include inherited
   work when the branch comparison contains more than the latest increment.
4. Require applicable CI to pass and follow any repository protection or
   review rules. Do not bypass failing checks or required approvals.
5. Merge completed work using a merge commit. Scientific receipts and offline
   tests may require the original commits to remain ancestors of HEAD; squash
   or rebase integration can break this provenance.
6. Verify CI on the merged main revision. Continue new research in a scoped
   branch from that revision. Preserve branches when still useful for audit.

The user authorized ordinary integration for the agreed project work on
2026-09-11. This workflow does not authorize deployment, force pushes, changes
to branch protections, new scientific campaigns without their required plans,
or relaxing a failed scientific criterion.

Source manifests bind bytes, including historical line endings. Files named
in those manifests must retain their recorded checkout bytes on Windows and
Linux. The provenance regression checks every current study and the fixed
validation plan; the explicitly superseded S2a v1 remains bound to its old
checkpoint. Do not normalize frozen sources or update expected hashes to hide
a checkout conversion. Preserve the original byte stream and pin its Git
attributes instead.

The active delivery objective is in
[GENERAL_VERIFICATION_WORKFLOW.md](GENERAL_VERIFICATION_WORKFLOW.md) and root
AGENTS.md. The preserved [SCIENTIFIC_ROADMAP.md](SCIENTIFIC_ROADMAP.md) supplies
the research requirements. Public deployment, target acquisition for S3 and
physical qualification remain separate from Git integration.
