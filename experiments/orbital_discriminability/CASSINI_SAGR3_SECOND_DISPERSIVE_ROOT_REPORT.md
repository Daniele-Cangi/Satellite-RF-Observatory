# Cassini SAGR3 second dispersive-root audit

## Outcome

`NO_SECOND_DISPERSIVE_ROOT_AVAILABLE`

This is a bounded metadata result, not a global absence claim. No RSR label,
header, payload, IQ, sample, amplitude, or detector input was accessed.

## Physical question

Can the frozen pre-transition pass support

`DSS25 X/Ka - DSS65 X/Ka`

so that first-order cold-plasma terms are removed independently at both
geographic receive roots?

The existing DSS25 X/Ka pair can define the first common coordinate. A
simultaneous DSS65 Ka branch is required for the second. Exact carrier grids
alone cannot manufacture a missing measurement branch.

## Bounded evidence

The official [SAGR3 bundle index](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/)
names exactly two raw-RSR collections: `data-rsr01` and `data-rsr02`.

The hashed [RSR01 inventory](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr01/collection_sagr_rsr01.csv)
contains eight products for day 2006-251. The frozen 12:00 products are:

- DSS25 X: `s23sags2006_251_1200x14x25rd`;
- DSS25 Ka: `s23sags2006_251_1200x14k25rd`;
- DSS65 X: `s23sags2006_251_1200x14x65rd`.

There is no `k65rd` row. The hashed
[RSR02 inventory](https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/data-rsr02/collection_sagr_rsr02.csv)
contains no product from 2006-251.

The inventory snapshots are bound by SHA-256 in the receipt. Their full
contents were inspected in RAM and not persisted; the receipt retains the
eight matching RSR01 LIDVIDs and the zero-row RSR02 result.

## Consequence

The symmetric composed observable cannot be formed in this archived pass.
Therefore:

- DSS65 first-order plasma remains in the causal path;
- a negative orbital-versus-null result remains physically ambiguous;
- re-reading headers to materialize exact `fX(t)` and `fKa(t)` cannot close
  the missing-root cut;
- detector development or IQ access would not repair the topology.

The authorized claim is limited to the two hashed SAGR3 raw-RSR collection
snapshots. It does not assert that no DSS65 Ka recording exists elsewhere.

## Stop

Close the symmetric SAGR3 composite path without IQ access. The next satellite
experiment must choose a pass whose predeclared measurement set already
contains the physical coordinates needed to control propagation at every root,
rather than trying to recover them after selection.
