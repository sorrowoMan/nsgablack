# Benchmark Report

Generated: 2026-01-03T21:02:54

## Config
- seed_base: 42
- repeats: 3
- pop_size: 100
- generations: 80
- reference_points: 1000
- solvers: ['NSGA-II', 'NSGA-II + DiversityInit', 'NSGA-II + L2Bias', 'MOEA/D', 'MultiAgent', 'MultiAgent + ScoreBias']
- problems: ['ZDT1', 'ZDT3', 'DTLZ2']

## Summary (lower IGD is better, higher HV is better)
| Problem | Solver | IGD (mean +/- std) | HV (mean +/- std) | Pareto | Time(s) |
| --- | --- | --- | --- | --- | --- |
| ZDT1 | NSGA-II | 1.5673 +/- 0.1547 | 2.6881 +/- 0.5695 | 23.3 | 5.71 |
| ZDT1 | NSGA-II + DiversityInit | 1.4646 +/- 0.2123 | 2.3662 +/- 0.5432 | 30.0 | 5.19 |
| ZDT1 | NSGA-II + L2Bias | 1.6602 +/- 0.1799 | 2.2323 +/- 0.8398 | 20.7 | 23.63 |
| ZDT1 | MOEA/D | 2.4437 +/- 0.0491 | 1.4262 +/- 0.7160 | 29.7 | 4.70 |
| ZDT1 | MultiAgent | 2.4651 +/- 0.1289 | 0.7473 +/- 0.3956 | 17.3 | 57.41 |
| ZDT1 | MultiAgent + ScoreBias | 2.3773 +/- 0.1770 | 1.4145 +/- 0.2386 | 31.0 | 31.79 |
| ZDT3 | NSGA-II | 1.5468 +/- 0.1285 | 1.9209 +/- 0.2695 | 33.0 | 31.17 |
| ZDT3 | NSGA-II + DiversityInit | 1.7104 +/- 0.0342 | 2.0438 +/- 0.4588 | 27.3 | 4.19 |
| ZDT3 | NSGA-II + L2Bias | 1.6745 +/- 0.1735 | 2.1533 +/- 0.2247 | 33.7 | 7.53 |
| ZDT3 | MOEA/D | 2.2439 +/- 0.1093 | 1.1856 +/- 0.6096 | 11.0 | 0.72 |
| ZDT3 | MultiAgent | 2.2587 +/- 0.1504 | 1.2160 +/- 0.7610 | 31.0 | 43.11 |
| ZDT3 | MultiAgent + ScoreBias | 2.2810 +/- 0.2665 | 1.0094 +/- 0.2533 | 25.7 | 24.31 |
| DTLZ2 | NSGA-II | 0.1629 +/- 0.0150 | 1.0557 +/- 0.3398 | 45.0 | 11.83 |
| DTLZ2 | NSGA-II + DiversityInit | 0.1754 +/- 0.0109 | 0.7091 +/- 0.0510 | 37.3 | 14.03 |
| DTLZ2 | NSGA-II + L2Bias | 0.1567 +/- 0.0075 | 1.3036 +/- 0.6135 | 43.7 | 95.49 |
| DTLZ2 | MOEA/D | 0.2608 +/- 0.0137 | 0.7137 +/- 0.2378 | 31.7 | 3.77 |
| DTLZ2 | MultiAgent | 0.1205 +/- 0.0042 | 0.5119 +/- 0.1040 | 35.7 | 6.35 |
| DTLZ2 | MultiAgent + ScoreBias | 0.1215 +/- 0.0136 | 0.4627 +/- 0.0802 | 21.0 | 20.10 |

## Ranking by IGD
- DTLZ2: MultiAgent, MultiAgent + ScoreBias, NSGA-II + L2Bias
- ZDT1: NSGA-II + DiversityInit, NSGA-II, NSGA-II + L2Bias
- ZDT3: NSGA-II, NSGA-II + L2Bias, NSGA-II + DiversityInit

## Ranking by HV
- DTLZ2: NSGA-II + L2Bias, NSGA-II, MOEA/D
- ZDT1: NSGA-II, NSGA-II + DiversityInit, NSGA-II + L2Bias
- ZDT3: NSGA-II + L2Bias, NSGA-II + DiversityInit, NSGA-II

## Notes
- HV is computed for 2 objectives only.
- Bias variants are not strictly comparable to unbiased baselines.

## Conclusions
- [ ] Fill in observations and decisions.

## Next Steps
- [ ] Add more solvers or bias combinations.