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

The active scientific objective remains in [SCIENTIFIC_ROADMAP.md](SCIENTIFIC_ROADMAP.md)
and root AGENTS.md. Website development, target acquisition for S3 and physical
qualification remain separate from Git integration.
