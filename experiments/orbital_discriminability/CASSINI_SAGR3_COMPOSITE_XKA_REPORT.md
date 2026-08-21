# Cassini SAGR3 DSS-25 X/Ka composite audit

## Outcome

`CASSINI_COMPOSITE_OBSERVABLE_NOT_ADMITTED`

The proposed observable is mathematically useful but is not yet a physical RF
measurement.  No network, RSR header, IQ, sample, amplitude, or detector input
was accessed during this audit.

Parent receipt identities use repository-text SHA-256: checkout `CRLF` is
normalized to the Git-blob `LF` representation before hashing. JSON content
and all scientific fields remain byte-sensitive after that explicit EOL rule.

## What survives

For simultaneous fractional-frequency coordinates

`z_station,band = g_station + p_station / f_band^2 + h_station,band`,

the DSS-25 weights

- `w25X = -fX^2 / (fKa^2 - fX^2)`;
- `w25Ka = fKa^2 / (fKa^2 - fX^2)`

satisfy both `w25X + w25Ka = 1` and
`w25X/fX^2 + w25Ka/fKa^2 = 0`.  They therefore preserve the common DSS-25
fractional Doppler and cancel a first-order cold-plasma term on that path.  The
distributed observable would be

`C = fX * (w25X*z25X + w25Ka*z25Ka - z65X)`.

At the nominal frozen carriers the diagnostic weights are approximately
`-0.07433988385143721` and `1.0743398838514373`.  These nominal values are not
a substitute for the exact time-varying X/Ka carrier coordinates.

The composite retains exactly one prefix-only constant-plus-linear nuisance
fit after composition.  Per-band affine fits and suffix refits remain
prohibited.  By linear identity, the same prefix-affine and Saturn-barycenter
geometry-destroying nulls apply.  The controlling geometry cannot grow: it
remains **0.07231370056321107 Hz peak-to-peak**, with the existing
`0.000007482903185973555 Hz` timing envelope.  This is inherited geometry, not
a new RF result.

## Why physical admission fails

The frozen aggregate header receipt proves simultaneous, continuous, distinct
DSS-25 X/Ka channels, but retains only transform clauses and LO/DDC summaries.
It does not retain the exact per-record sky-carrier/polynomial grid needed to
apply the dispersive weights on the real coordinate.  Reusing nominal carriers
would silently turn an exact invariant into an approximation.

Even if that grid were materialized, the composition only removes the
first-order dispersive contribution at DSS-25.  It leaves:

- DSS-65 cold plasma, because DSS-65 has only X in the frozen set;
- differential troposphere;
- receiver proper-time/gravity differential;
- the still-unbounded relativistic propagation remainder;
- `w25X*h25X + w25Ka*h25Ka - h65X`, a cross-band and cross-station hardware
  term.

The X/Ka pair also has not observed plasma yet: without IQ, “plasma measured”
is not an authorized statement.  The exact authorized statement is only that
the composition algebra is valid for exact simultaneous sky-frequency
coordinates.

## Scientific consequence

The thesis is correct in direction: a composed observable is the next physical
question, and the pre-transition single-observable path should remain closed.
But the frozen receipts do not yet make the composed negative interpretable.
The transformation has passed its algebraic audit; the physical observable has
not passed admission.  No detector or IQ access follows from this result.
