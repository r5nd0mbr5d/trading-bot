# Candidate Bundle Template

This folder is a scaffold for a real research candidate bundle used by
`python main.py research_register_candidate`.

## Required Files

- candidate.json
  - Required fields: name, version, strategy_type, parameters, experiment_id, artifact_sha256

## Optional Files

- model.pt
  - Required only when strategy_type is "nn".
  - If present, artifact_sha256 must match the SHA256 of model.pt.

## Example Usage

```bash
python main.py research_register_candidate \
  --candidate-dir research/experiments/<experiment_id> \
  --registry-db-path trading.db \
  --artifacts-dir strategies \
  --output-dir research/experiments/<experiment_id>
```
