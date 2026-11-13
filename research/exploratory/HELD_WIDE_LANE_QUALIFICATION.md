# Held wide-lane qualification

Use this workflow when a provider can release calibration labels and held
measurements first, then independently release the held labels. For a new
physical claim, set the decision scope and the held arc roster before looking
at values. Choose the grouping, transfer allowance and error bounds from
independent calibration or measurement specifications. Record them with
receiver and signal identities, phase convention, DD sign, epoch alignment
and acquisition or reacquisition boundaries. Review calibration and validation
arc membership using source provenance. Unique row IDs also prevent accidental
reuse of the same record ID.

Measurements use the JSON groups described in the
[initial calibration study](known-wide-lane-2026-11-12/RESULTS.md).
Each group shares one calibration bias interval and one declared transfer
allowance. Include every scheduled validation ID. If an arc is unavailable
because of a missing observation or loss of continuity, supply its ID and
unavailable_reason instead of mean_cycles and halfwidth_cycles.

    python -m research.exploratory.known_wide_lane --prepare-only --measurements measurements.json --output data/held-wide-lane-predictions

Record or share the printed predictions.json SHA-256 before receiving the
held labels. The prediction file includes the measurements digest, held
means and error halfwidths, the calibration interval, and each candidate set.
The prepare command has no access to the label file. Use the separately
recorded digest for evaluation.

    python -m research.exploratory.known_wide_lane --score-predictions data/held-wide-lane-predictions/predictions.json --expected-predictions-sha256 RECORDED_SHA256 --truth labels.json --output data/held-wide-lane-scores

The labels file maps each measured validation ID to an independent integer,
or to null when the provider could not establish one. Omit unavailable
measurement IDs from the labels file. A singleton without a label is kept
as unlabelled. A missing or extra ID or a duplicate JSON key invalidates the
label file. The scorer verifies the prediction digest before reading truth.

On a labelled held arc, the measured MW mean minus the integer gives an
interval for the effective bias under its admitted measurement error bound.
Subtract the full calibration interval to obtain a conservative interval
for bias change. The scorer distinguishes intervals wholly within the
declared allowance, wholly outside it, and those overlapping its boundary.
An unknown transfer allowance or inconsistent calibration is unqualified.
Use jointly valid measurement bounds for the claimed scope. A collection of
nominal per-arc intervals does not by itself establish joint confidence.
Report dependency across arcs sharing a receiver, satellite or run when
estimating a population error rate. This workflow evaluates the supplied
bounds and labels. Their physical validity comes from the source evidence.
