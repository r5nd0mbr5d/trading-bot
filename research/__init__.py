"""
Research package for trading-bot.

Contains data pipelines, feature engineering, model training, and
experiment orchestration for strategy research and validation.

Modules:
- data: Historical bar fetching, feature/label engineering, data splits
- models: Model training artifacts (XGBoost, LSTM, etc.)
- experiments: Experiment pipelines and orchestration
- bridge: Runtime integration bridges (limited, TYPE_CHECKING only to avoid circular imports)
- specs: Configuration specs and policy documents
"""
