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
