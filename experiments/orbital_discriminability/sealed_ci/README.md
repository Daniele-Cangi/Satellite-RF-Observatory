# Cassini regression coverage

`test_cassini_predict_spk.py` is the original, non-optional three-epoch
regression restored after its replacement by a simulator reduced coverage.
It uses actual CSPICE and the four exact-hash public JPL kernels. Set
`SATELLITE_RF_CASSINI_KERNEL_ROOT` to their directory; missing kernels,
missing dependencies or altered bytes must fail, never skip or fall back.
The dedicated CI workflow downloads them with bounded retries and checks
their hashes before running this directory.

`test_cassini_synthetic_compiler.py` is an additional synthetic consistency
check. Its invented states are constructed from expected light times and
frequency factors; it cannot validate kernel decoding, time conversion,
station frames or the real spacecraft trajectory. Its lineage objects are
mocked metadata, not evidence that kernel bytes were read.

Local restoration check on 2026-09-13: all four downloaded hashes matched;
the real regression and two synthetic/contract checks passed with NumPy
2.3.3 and spiceypy 7.0.0. This restores software regression coverage, without
changing the historical experiment or adding physical confirmation.
