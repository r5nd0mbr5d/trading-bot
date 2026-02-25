# Research Experiment Specification

## 1. Pre-Registration Discipline

State the hypothesis (features, target, model) before running an experiment. Do not back-fill the hypothesis after seeing results.

Required hypothesis fields for experiment configs:
- `hypothesis_id`
- `hypothesis_text`
- `n_prior_tests`
- `registered_before_test`

## 2. Class-Imbalance Discipline

For binary classifiers, compute class balance from the training fold and pass `scale_pos_weight` to the learner.

For future LSTM training, use:
- `torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor([scale_pos_weight]))`

Class balancing is training-fold only; never rebalance validation/test folds.

## 3. Claim-Integrity Metadata Discipline

Every experiment that reports performance claims must include claim-integrity
metadata in its config/results pipeline:

- `out_of_sample_period`
- `transaction_costs_slippage_assumptions`
- `max_drawdown`
- `turnover`
- `tested_variants`

Missing fields do not hard-fail promotion checks yet, but they must emit
`CAUTION` flags for reviewer attention. Claims with annualized return > 100%
and incomplete claim-integrity metadata must include
`high_return_claim_unverified` in promotion outputs.

## 4. Benchmark Comparison Discipline

Where applicable, ML experiments should be compared against the
`pairs_mean_reversion` benchmark strategy before promotion discussion.
If a pair-style hypothesis is proposed, include benchmark-vs-ML comparison
in the experiment summary (return, drawdown, and PR-AUC where relevant).
