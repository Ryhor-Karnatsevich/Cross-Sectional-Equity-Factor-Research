# Factor Selection Report

![Factor Selection summary](Figures/factor_selection_summary.png)

## Scope

- Factor configurations analyzed: `56`.
- Factor-horizon hypotheses analyzed: `448`.
- Effect tests analyzed: `2240`.
- Full 448-hypothesis scope: `yes`.
- Primary correction: Benjamini-Hochberg applied separately within each of the five effect families at 5% FDR.
- Each complete family contains 448 factor-horizon tests. FDR control applies within each family, not to their pooled discoveries.
- Pooled global BH is retained in effect_tests.csv as a comparison; active-scope columns refer to the primary per-effect correction.

## Pattern Classification

- `no_stable_structure`: 408 hypotheses.
- `upper_tail`: 29 hypotheses.
- `lower_tail`: 9 hypotheses.
- `positive_monotonic`: 2 hypotheses.

## Evidence Status

- `no_stable_structure`: 408 hypotheses.
- `rejected_by_multiple_testing`: 24 hypotheses.
- `time_unstable_pattern`: 16 hypotheses.

## Final Layer Decision

- Rank-IC discoveries after per-effect FDR: `22`.
- Economic-effect discoveries after per-effect FDR: `0`.
- Final economic candidates: `0`.

Layer 3 found statistical cross-sectional rank evidence, but no economic return pattern survived the complete selection rules.

## Economic Pattern Cards

The table shows up to 50 detected patterns. Complete results remain in `hypothesis_cards.csv` and `effect_tests.csv`.

| Hypothesis | Pattern | Strongest economic effect | Q10-Q1 mean / t | Q10-middle mean / t | Middle-Q1 mean / t | Edges-middle mean / t | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| liquidity_change\|liq_20d_252d / h252 | upper_tail | q10_minus_middle | 0.0023 / 0.15 | 0.0168 / 2.63 | -0.0145 / -0.97 | 0.0157 / 1.78 | rejected_by_multiple_testing |
| residual_momentum\|resmom_9m_1m / h63 | upper_tail | q10_minus_middle | 0.0137 / 1.62 | 0.0111 / 2.55 | 0.0027 / 0.40 | 0.0042 / 1.13 | rejected_by_multiple_testing |
| residual_momentum\|resmom_9m_1m / h42 | upper_tail | q10_minus_middle | 0.0087 / 1.45 | 0.0073 / 2.37 | 0.0014 / 0.31 | 0.0029 / 1.17 | rejected_by_multiple_testing |
| residual_momentum\|resmom_12m_1m / h252 | upper_tail | q10_minus_middle | 0.0392 / 1.20 | 0.0326 / 2.34 | 0.0066 / 0.23 | 0.0130 / 0.81 | rejected_by_multiple_testing |
| liquidity_change\|liq_20d_126d / h252 | upper_tail | q10_minus_middle | 0.0062 / 0.77 | 0.0133 / 2.46 | -0.0071 / -0.71 | 0.0102 / 1.47 | rejected_by_multiple_testing |
| momentum\|18m-1m / h126 | upper_tail | q10_minus_middle | 0.0277 / 1.38 | 0.0212 / 2.50 | 0.0065 / 0.42 | 0.0074 / 0.98 | time_unstable_pattern |
| momentum\|18m-0m / h126 | upper_tail | q10_minus_middle | 0.0264 / 1.32 | 0.0202 / 2.43 | 0.0062 / 0.40 | 0.0070 / 0.93 | time_unstable_pattern |
| liquidity_change\|liq_20d_252d / h126 | upper_tail | q10_minus_middle | 0.0090 / 1.08 | 0.0136 / 2.20 | -0.0046 / -0.81 | 0.0091 / 2.18 | rejected_by_multiple_testing |
| liquidity_change\|liq_20d_126d / h126 | upper_tail | edges_minus_middle | 0.0065 / 1.12 | 0.0104 / 2.13 | -0.0039 / -1.04 | 0.0072 / 2.19 | rejected_by_multiple_testing |
| momentum\|18m-2m / h126 | upper_tail | q10_minus_middle | 0.0248 / 1.24 | 0.0197 / 2.34 | 0.0050 / 0.33 | 0.0074 / 0.99 | time_unstable_pattern |
| momentum\|9m-2m / h63 | upper_tail | q10_minus_middle | 0.0124 / 1.37 | 0.0106 / 2.20 | 0.0017 / 0.25 | 0.0045 / 1.18 | rejected_by_multiple_testing |
| low_volatility\|60d / h63 | lower_tail | edges_minus_middle | -0.0170 / -1.52 | -0.0005 / -0.09 | -0.0165 / -2.19 | 0.0080 / 2.52 | rejected_by_multiple_testing |
| price_volume_confirmation\|pvc_9m_1m_liq20_126 / h63 | upper_tail | q10_minus_middle | 0.0111 / 1.27 | 0.0093 / 2.14 | 0.0018 / 0.27 | 0.0037 / 1.01 | rejected_by_multiple_testing |
| momentum\|6m-1m / h126 | upper_tail | q10_minus_middle | 0.0251 / 1.66 | 0.0189 / 2.08 | 0.0062 / 0.57 | 0.0064 / 0.97 | rejected_by_multiple_testing |
| residual_momentum\|resmom_9m_1m / h126 | upper_tail | q10_minus_middle | 0.0280 / 1.54 | 0.0191 / 2.10 | 0.0089 / 0.63 | 0.0051 / 0.67 | rejected_by_multiple_testing |
| low_volatility\|60d / h42 | lower_tail | edges_minus_middle | -0.0116 / -1.51 | -0.0003 / -0.10 | -0.0113 / -2.19 | 0.0055 / 2.62 | time_unstable_pattern |
| liquidity_change\|liq_20d_126d / h42 | lower_tail | middle_minus_q1 | -0.0026 / -1.06 | 0.0010 / 0.60 | -0.0036 / -2.12 | 0.0023 / 2.03 | rejected_by_multiple_testing |
| momentum\|9m-1m / h63 | upper_tail | q10_minus_middle | 0.0121 / 1.35 | 0.0097 / 2.12 | 0.0025 / 0.36 | 0.0036 / 0.96 | rejected_by_multiple_testing |
| residual_momentum\|resmom_12m_1m / h126 | upper_tail | q10_minus_middle | 0.0291 / 1.62 | 0.0180 / 2.05 | 0.0111 / 0.75 | 0.0035 / 0.43 | rejected_by_multiple_testing |
| momentum\|9m-1m / h42 | upper_tail | q10_minus_middle | 0.0079 / 1.26 | 0.0065 / 2.00 | 0.0014 / 0.30 | 0.0025 / 1.00 | rejected_by_multiple_testing |
| momentum\|6m-0m / h126 | upper_tail | q10_minus_middle | 0.0254 / 1.61 | 0.0188 / 2.04 | 0.0065 / 0.57 | 0.0062 / 0.91 | rejected_by_multiple_testing |
| residual_momentum\|resmom_9m_1m / h5 | upper_tail | q10_minus_middle | 0.0008 / 0.96 | 0.0009 / 1.96 | -0.0001 / -0.10 | 0.0005 / 1.49 | rejected_by_multiple_testing |
| short_term_reversal\|reversal_5d / h5 | upper_tail | q10_minus_middle | 0.0013 / 1.76 | 0.0010 / 1.98 | 0.0003 / 0.76 | 0.0003 / 1.29 | rejected_by_multiple_testing |
| momentum\|9m-0m / h63 | upper_tail | q10_minus_middle | 0.0119 / 1.30 | 0.0090 / 2.02 | 0.0029 / 0.41 | 0.0031 / 0.85 | rejected_by_multiple_testing |
| low_volatility\|90d / h63 | lower_tail | edges_minus_middle | -0.0172 / -1.49 | -0.0013 / -0.24 | -0.0159 / -2.06 | 0.0073 / 2.25 | time_unstable_pattern |
| low_volatility\|90d / h42 | lower_tail | edges_minus_middle | -0.0115 / -1.46 | -0.0007 / -0.20 | -0.0108 / -2.07 | 0.0050 / 2.37 | time_unstable_pattern |
| price_volume_confirmation\|pvc_6m_1m_liq5_60 / h126 | upper_tail | q10_minus_middle | 0.0241 / 1.62 | 0.0179 / 2.01 | 0.0061 / 0.58 | 0.0059 / 0.92 | rejected_by_multiple_testing |
| momentum\|9m-2m / h42 | upper_tail | q10_minus_middle | 0.0077 / 1.27 | 0.0067 / 2.02 | 0.0010 / 0.21 | 0.0029 / 1.11 | rejected_by_multiple_testing |
| residual_momentum\|resmom_6m_1m / h126 | positive_monotonic | q10_minus_middle | 0.0276 / 1.97 | 0.0201 / 2.34 | 0.0075 / 0.73 | 0.0063 / 0.98 | rejected_by_multiple_testing |
| momentum\|18m-1m / h63 | upper_tail | q10_minus_middle | 0.0119 / 1.25 | 0.0095 / 2.09 | 0.0024 / 0.33 | 0.0035 / 0.94 | time_unstable_pattern |
| low_volatility\|40d / h63 | lower_tail | edges_minus_middle | -0.0162 / -1.49 | -0.0016 / -0.33 | -0.0145 / -1.99 | 0.0064 / 2.12 | time_unstable_pattern |
| liquidity_change\|liq_20d_126d / h1 | lower_tail | middle_minus_q1 | -0.0001 / -1.23 | 0.0000 / 0.08 | -0.0001 / -1.98 | 0.0001 / 1.45 | rejected_by_multiple_testing |
| short_term_reversal\|reversal_5d / h1 | positive_monotonic | q10_minus_middle | 0.0004 / 2.03 | 0.0003 / 2.07 | 0.0001 / 1.17 | 0.0001 / 0.97 | time_unstable_pattern |
| momentum\|6m-2m / h126 | upper_tail | q10_minus_middle | 0.0249 / 1.73 | 0.0173 / 1.97 | 0.0076 / 0.74 | 0.0048 / 0.77 | time_unstable_pattern |
| price_volume_confirmation\|pvc_12m_1m_liq20_252 / h252 | upper_tail | q10_minus_middle | 0.0356 / 1.02 | 0.0300 / 1.99 | 0.0056 / 0.19 | 0.0122 / 0.81 | time_unstable_pattern |
| residual_momentum\|resmom_9m_1m / h252 | upper_tail | q10_minus_middle | 0.0351 / 1.16 | 0.0293 / 2.01 | 0.0058 / 0.22 | 0.0118 / 0.81 | time_unstable_pattern |
| low_volatility\|180d / h42 | lower_tail | edges_minus_middle | -0.0127 / -1.54 | -0.0018 / -0.49 | -0.0109 / -1.96 | 0.0045 / 2.00 | time_unstable_pattern |
| momentum\|18m-2m / h63 | upper_tail | q10_minus_middle | 0.0112 / 1.17 | 0.0097 / 2.02 | 0.0015 / 0.21 | 0.0041 / 1.08 | time_unstable_pattern |
| liquidity_change\|liq_20d_126d / h5 | lower_tail | middle_minus_q1 | -0.0005 / -1.35 | 0.0000 / 0.15 | -0.0006 / -2.01 | 0.0003 / 1.67 | time_unstable_pattern |
| momentum\|18m-0m / h63 | upper_tail | q10_minus_middle | 0.0112 / 1.17 | 0.0090 / 2.00 | 0.0022 / 0.29 | 0.0034 / 0.90 | time_unstable_pattern |

## IC and Stability Diagnostics

IC is reported as supporting information. It does not create a candidate when no economic pattern is detected.

| Horizon | Pattern | Direction | Mean IC | IC HAC t | Primary effect | Effect mean | Effect HAC t | Monthly stability | Annual stability | Rank autocorr | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| liquidity_change\|liq_20d_126d / h1 | lower_tail | q1_above_middle | -0.0023 | -1.58 | middle_minus_q1 | -0.0001 | -1.98 | 0.56 | 0.71 | 0.99 | rejected_by_multiple_testing |
| liquidity_change\|liq_20d_126d / h5 | lower_tail | q1_above_middle | -0.0058 | -2.27 | middle_minus_q1 | -0.0006 | -2.01 | 0.57 | 0.59 | 0.86 | time_unstable_pattern |
| liquidity_change\|liq_20d_126d / h42 | lower_tail | q1_above_middle | -0.0096 | -1.74 | middle_minus_q1 | -0.0036 | -2.12 | 0.55 | 0.71 | 0.04 | rejected_by_multiple_testing |
| liquidity_change\|liq_20d_126d / h126 | upper_tail | q10_above_middle | 0.0002 | 0.04 | q10_minus_middle | 0.0104 | 2.13 | 0.61 | 0.76 | 0.06 | rejected_by_multiple_testing |
| liquidity_change\|liq_20d_126d / h252 | upper_tail | q10_above_middle | 0.0050 | 0.90 | q10_minus_middle | 0.0133 | 2.46 | 0.62 | 0.62 | 0.14 | rejected_by_multiple_testing |
| liquidity_change\|liq_20d_252d / h126 | upper_tail | q10_above_middle | 0.0063 | 0.78 | q10_minus_middle | 0.0136 | 2.20 | 0.61 | 0.71 | 0.12 | rejected_by_multiple_testing |
| liquidity_change\|liq_20d_252d / h252 | upper_tail | q10_above_middle | 0.0102 | 1.03 | q10_minus_middle | 0.0168 | 2.63 | 0.65 | 0.75 | 0.07 | rejected_by_multiple_testing |
| low_volatility\|180d / h42 | lower_tail | q1_above_middle | -0.0044 | -0.22 | middle_minus_q1 | -0.0109 | -1.96 | 0.50 | 0.71 | 0.96 | time_unstable_pattern |
| low_volatility\|40d / h63 | lower_tail | q1_above_middle | -0.0007 | -0.03 | middle_minus_q1 | -0.0145 | -1.99 | 0.55 | 0.71 | 0.68 | time_unstable_pattern |
| low_volatility\|60d / h42 | lower_tail | q1_above_middle | -0.0031 | -0.16 | middle_minus_q1 | -0.0113 | -2.19 | 0.54 | 0.65 | 0.81 | time_unstable_pattern |
| low_volatility\|60d / h63 | lower_tail | q1_above_middle | -0.0029 | -0.13 | middle_minus_q1 | -0.0165 | -2.19 | 0.56 | 0.65 | 0.73 | rejected_by_multiple_testing |
| low_volatility\|90d / h42 | lower_tail | q1_above_middle | -0.0052 | -0.27 | middle_minus_q1 | -0.0108 | -2.07 | 0.54 | 0.71 | 0.88 | time_unstable_pattern |
| low_volatility\|90d / h63 | lower_tail | q1_above_middle | -0.0046 | -0.20 | middle_minus_q1 | -0.0159 | -2.06 | 0.55 | 0.71 | 0.83 | time_unstable_pattern |
| momentum\|18m-0m / h63 | upper_tail | q10_above_middle | 0.0125 | 0.68 | q10_minus_middle | 0.0090 | 2.00 | 0.56 | 0.59 | 0.80 | time_unstable_pattern |
| momentum\|18m-0m / h126 | upper_tail | q10_above_middle | 0.0235 | 0.92 | q10_minus_middle | 0.0202 | 2.43 | 0.62 | 0.59 | 0.62 | time_unstable_pattern |
| momentum\|18m-1m / h63 | upper_tail | q10_above_middle | 0.0139 | 0.76 | q10_minus_middle | 0.0095 | 2.09 | 0.57 | 0.59 | 0.79 | time_unstable_pattern |
| momentum\|18m-1m / h126 | upper_tail | q10_above_middle | 0.0240 | 0.93 | q10_minus_middle | 0.0212 | 2.50 | 0.65 | 0.53 | 0.60 | time_unstable_pattern |
| momentum\|18m-2m / h63 | upper_tail | q10_above_middle | 0.0153 | 0.83 | q10_minus_middle | 0.0097 | 2.02 | 0.56 | 0.59 | 0.78 | time_unstable_pattern |
| momentum\|18m-2m / h126 | upper_tail | q10_above_middle | 0.0237 | 0.91 | q10_minus_middle | 0.0197 | 2.34 | 0.62 | 0.47 | 0.58 | time_unstable_pattern |
| momentum\|6m-0m / h126 | upper_tail | q10_above_middle | 0.0213 | 1.24 | q10_minus_middle | 0.0188 | 2.04 | 0.65 | 0.65 | 0.02 | rejected_by_multiple_testing |
| momentum\|6m-1m / h126 | upper_tail | q10_above_middle | 0.0215 | 1.25 | q10_minus_middle | 0.0189 | 2.08 | 0.65 | 0.65 | 0.01 | rejected_by_multiple_testing |
| momentum\|6m-2m / h126 | upper_tail | q10_above_middle | 0.0238 | 1.44 | q10_minus_middle | 0.0173 | 1.97 | 0.63 | 0.59 | 0.01 | time_unstable_pattern |
| momentum\|9m-0m / h63 | upper_tail | q10_above_middle | 0.0142 | 0.88 | q10_minus_middle | 0.0090 | 2.02 | 0.59 | 0.71 | 0.64 | rejected_by_multiple_testing |
| momentum\|9m-1m / h42 | upper_tail | q10_above_middle | 0.0113 | 0.82 | q10_minus_middle | 0.0065 | 2.00 | 0.60 | 0.76 | 0.72 | rejected_by_multiple_testing |
| momentum\|9m-1m / h63 | upper_tail | q10_above_middle | 0.0151 | 0.95 | q10_minus_middle | 0.0097 | 2.12 | 0.59 | 0.65 | 0.60 | rejected_by_multiple_testing |
| momentum\|9m-2m / h42 | upper_tail | q10_above_middle | 0.0122 | 0.90 | q10_minus_middle | 0.0067 | 2.02 | 0.56 | 0.71 | 0.68 | rejected_by_multiple_testing |
| momentum\|9m-2m / h63 | upper_tail | q10_above_middle | 0.0169 | 1.04 | q10_minus_middle | 0.0106 | 2.20 | 0.57 | 0.65 | 0.54 | rejected_by_multiple_testing |
| price_volume_confirmation\|pvc_12m_1m_liq20_252 / h252 | upper_tail | q10_above_middle | 0.0186 | 0.64 | q10_minus_middle | 0.0300 | 1.99 | 0.62 | 0.56 | -0.01 | time_unstable_pattern |
| price_volume_confirmation\|pvc_6m_1m_liq5_60 / h126 | upper_tail | q10_above_middle | 0.0213 | 1.24 | q10_minus_middle | 0.0179 | 2.01 | 0.64 | 0.65 | 0.01 | rejected_by_multiple_testing |
| price_volume_confirmation\|pvc_9m_1m_liq20_126 / h63 | upper_tail | q10_above_middle | 0.0143 | 0.91 | q10_minus_middle | 0.0093 | 2.14 | 0.60 | 0.65 | 0.58 | rejected_by_multiple_testing |
| residual_momentum\|resmom_12m_1m / h126 | upper_tail | q10_above_middle | 0.0224 | 1.00 | q10_minus_middle | 0.0180 | 2.05 | 0.60 | 0.71 | 0.42 | rejected_by_multiple_testing |
| residual_momentum\|resmom_12m_1m / h252 | upper_tail | q10_above_middle | 0.0232 | 0.85 | q10_minus_middle | 0.0326 | 2.34 | 0.66 | 0.75 | -0.00 | rejected_by_multiple_testing |
| residual_momentum\|resmom_6m_1m / h126 | positive_monotonic | positive | 0.0251 | 1.55 | q10_minus_q1 | 0.0276 | 1.97 | 0.63 | 0.65 | 0.02 | rejected_by_multiple_testing |
| residual_momentum\|resmom_9m_1m / h5 | upper_tail | q10_above_middle | 0.0106 | 1.79 | q10_minus_middle | 0.0009 | 1.96 | 0.61 | 0.76 | 0.96 | rejected_by_multiple_testing |
| residual_momentum\|resmom_9m_1m / h42 | upper_tail | q10_above_middle | 0.0135 | 1.00 | q10_minus_middle | 0.0073 | 2.37 | 0.61 | 0.82 | 0.72 | rejected_by_multiple_testing |
| residual_momentum\|resmom_9m_1m / h63 | upper_tail | q10_above_middle | 0.0179 | 1.18 | q10_minus_middle | 0.0111 | 2.55 | 0.59 | 0.71 | 0.59 | rejected_by_multiple_testing |
| residual_momentum\|resmom_9m_1m / h126 | upper_tail | q10_above_middle | 0.0267 | 1.26 | q10_minus_middle | 0.0191 | 2.10 | 0.63 | 0.65 | 0.25 | rejected_by_multiple_testing |
| residual_momentum\|resmom_9m_1m / h252 | upper_tail | q10_above_middle | 0.0239 | 0.94 | q10_minus_middle | 0.0293 | 2.01 | 0.61 | 0.56 | -0.00 | time_unstable_pattern |
| short_term_reversal\|reversal_5d / h1 | positive_monotonic | positive | 0.0072 | 2.54 | q10_minus_q1 | 0.0004 | 2.03 | 0.55 | 0.65 | 0.76 | time_unstable_pattern |
| short_term_reversal\|reversal_5d / h5 | upper_tail | q10_above_middle | 0.0119 | 2.75 | q10_minus_middle | 0.0010 | 1.98 | 0.59 | 0.76 | -0.01 | rejected_by_multiple_testing |

## Figures

### Hypothesis Overview

![hypothesis overview](Figures/hypothesis_overview.png)

### Liquidity Change  Liq 20D 252D  Evidence Dashboard

![liquidity change  liq 20d 252d  evidence dashboard](Figures/liquidity_change__liq_20d_252d__evidence_dashboard.png)

### Liquidity Change  Liq 20D 252D  Quantile Curves

![liquidity change  liq 20d 252d  quantile curves](Figures/liquidity_change__liq_20d_252d__quantile_curves.png)

### Liquidity Change  Liq 20D 252D  Monthly Ic

![liquidity change  liq 20d 252d  monthly ic](Figures/liquidity_change__liq_20d_252d__monthly_ic.png)

### Residual Momentum  Resmom 9M 1M  Evidence Dashboard

![residual momentum  resmom 9m 1m  evidence dashboard](Figures/residual_momentum__resmom_9m_1m__evidence_dashboard.png)

### Residual Momentum  Resmom 9M 1M  Quantile Curves

![residual momentum  resmom 9m 1m  quantile curves](Figures/residual_momentum__resmom_9m_1m__quantile_curves.png)

### Residual Momentum  Resmom 9M 1M  Monthly Ic

![residual momentum  resmom 9m 1m  monthly ic](Figures/residual_momentum__resmom_9m_1m__monthly_ic.png)

### Residual Momentum  Resmom 12M 1M  Evidence Dashboard

![residual momentum  resmom 12m 1m  evidence dashboard](Figures/residual_momentum__resmom_12m_1m__evidence_dashboard.png)

### Residual Momentum  Resmom 12M 1M  Quantile Curves

![residual momentum  resmom 12m 1m  quantile curves](Figures/residual_momentum__resmom_12m_1m__quantile_curves.png)

### Residual Momentum  Resmom 12M 1M  Monthly Ic

![residual momentum  resmom 12m 1m  monthly ic](Figures/residual_momentum__resmom_12m_1m__monthly_ic.png)

### Liquidity Change  Liq 20D 126D  Evidence Dashboard

![liquidity change  liq 20d 126d  evidence dashboard](Figures/liquidity_change__liq_20d_126d__evidence_dashboard.png)

### Liquidity Change  Liq 20D 126D  Quantile Curves

![liquidity change  liq 20d 126d  quantile curves](Figures/liquidity_change__liq_20d_126d__quantile_curves.png)

### Liquidity Change  Liq 20D 126D  Monthly Ic

![liquidity change  liq 20d 126d  monthly ic](Figures/liquidity_change__liq_20d_126d__monthly_ic.png)

### Momentum  18M-1M  Evidence Dashboard

![momentum  18m-1m  evidence dashboard](Figures/momentum__18m-1m__evidence_dashboard.png)

### Momentum  18M-1M  Quantile Curves

![momentum  18m-1m  quantile curves](Figures/momentum__18m-1m__quantile_curves.png)

### Momentum  18M-1M  Monthly Ic

![momentum  18m-1m  monthly ic](Figures/momentum__18m-1m__monthly_ic.png)

### Momentum  18M-0M  Evidence Dashboard

![momentum  18m-0m  evidence dashboard](Figures/momentum__18m-0m__evidence_dashboard.png)

### Momentum  18M-0M  Quantile Curves

![momentum  18m-0m  quantile curves](Figures/momentum__18m-0m__quantile_curves.png)

### Momentum  18M-0M  Monthly Ic

![momentum  18m-0m  monthly ic](Figures/momentum__18m-0m__monthly_ic.png)

### Momentum  18M-2M  Evidence Dashboard

![momentum  18m-2m  evidence dashboard](Figures/momentum__18m-2m__evidence_dashboard.png)

### Momentum  18M-2M  Quantile Curves

![momentum  18m-2m  quantile curves](Figures/momentum__18m-2m__quantile_curves.png)

### Momentum  18M-2M  Monthly Ic

![momentum  18m-2m  monthly ic](Figures/momentum__18m-2m__monthly_ic.png)

### Momentum  9M-2M  Evidence Dashboard

![momentum  9m-2m  evidence dashboard](Figures/momentum__9m-2m__evidence_dashboard.png)

### Momentum  9M-2M  Quantile Curves

![momentum  9m-2m  quantile curves](Figures/momentum__9m-2m__quantile_curves.png)

### Momentum  9M-2M  Monthly Ic

![momentum  9m-2m  monthly ic](Figures/momentum__9m-2m__monthly_ic.png)

### Low Volatility  60D  Evidence Dashboard

![low volatility  60d  evidence dashboard](Figures/low_volatility__60d__evidence_dashboard.png)

### Low Volatility  60D  Quantile Curves

![low volatility  60d  quantile curves](Figures/low_volatility__60d__quantile_curves.png)

### Low Volatility  60D  Monthly Ic

![low volatility  60d  monthly ic](Figures/low_volatility__60d__monthly_ic.png)

### Price Volume Confirmation  Pvc 9M 1M Liq20 126  Evidence Dashboard

![price volume confirmation  pvc 9m 1m liq20 126  evidence dashboard](Figures/price_volume_confirmation__pvc_9m_1m_liq20_126__evidence_dashboard.png)

### Price Volume Confirmation  Pvc 9M 1M Liq20 126  Quantile Curves

![price volume confirmation  pvc 9m 1m liq20 126  quantile curves](Figures/price_volume_confirmation__pvc_9m_1m_liq20_126__quantile_curves.png)

### Price Volume Confirmation  Pvc 9M 1M Liq20 126  Monthly Ic

![price volume confirmation  pvc 9m 1m liq20 126  monthly ic](Figures/price_volume_confirmation__pvc_9m_1m_liq20_126__monthly_ic.png)

## Interpretation Rules

- `positive_monotonic` and `negative_monotonic` describe ordered Q1-Q10 relationships.
- `upper_tail` and `lower_tail` describe an effect concentrated in one extreme quantile.
- `both_tails_vs_middle` describes a U-shaped or inverted-U relationship.
- `no_stable_structure` means that no supported shape was identified by the current descriptive rules.
- A provisional candidate is not a validated trading strategy.
