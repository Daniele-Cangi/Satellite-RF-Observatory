# Causal GF/MW phase arc tracking

The tracker uses the existing GF prediction and the MW mean of up to ten
previous accepted samples in the active arc. The MW threshold is four times
the sample standard deviation with a floor of half a wide-lane cycle on the
scale. These parameters define the exploratory replay.
[ESA MW detector](https://gssc.esa.int/navipedia/index.php/Detector_based_in_code_and_carrier_phase_data%3A_The_Melbourne-W%C3%BCbbena_combination).

Either witness closes the arc and leaves the triggering sample without an arc
ID. The next usable sample starts a new arc with an unresolved ambiguity.
Unavailable samples and gaps also close the arc. Arc IDs are local to each
receiver/satellite link. Use phase differences between samples in the same arc.

The replay consumed 7,698 rows from six supported stations. The
[decision ledger](decisions.json.gz) retains each row's status and the YELL
header rejection.

| Decision | Rows |
|---|---:|
| Arc start | 99 |
| Arc continues | 7461 |
| Input unavailable | 130 |
| Witness break | 8 |

Five alerts were GF-only, two used both witnesses and one was MW-only. The
MW-only case was AREQ/G11 at GPST 36240 s with an innovation of 3.021 wide-lane
cycles. The physical cause and detection probabilities remain unqualified.

For BRAZ/G05, both witnesses fired at 10:59:30 GPST with LLI 0,0. The prediction
innovations were -15.895 m GF and -64.645 cycles MW. Arc 1 closed at that sample
and the 11:00 row started arc 2. The prefix test reproduces the same alert at
the end of the truncated stream. The synthetic 77/60 slip exercises MW when
the GF change cancels. Integer fixing still requires qualified bias and
uncertainty. The frozen forecasts and errors in #243 remain the held evaluation
record for that study.

Run the phase CLI from the repository root with a fresh output filename.

    python -m research.exploratory.real_phase --reference-arc-tracking --inputs research/exploratory/inputs/real_phase/observations_gps_only_v2.json --output data/reference-arc-tracking-2026-11-11.json.gz

The ledger binds the reference input hash and producer commit
49ef26d401edfc61c8ce1cc5fd3bb4c98f3f4f57. The producer Git blobs match the
recorded source hashes. Forty focused tests passed, including the previous
integer feasibility and MW stability replays.
