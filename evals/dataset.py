"""Evaluation dataset: topic strings for end-to-end literature review assessment."""

import json
from pathlib import Path

from deepeval.dataset import EvaluationDataset, Golden

_DATASET_PATH = Path(__file__).parent / "dataset.json"


def load_dataset() -> EvaluationDataset:
    with open(_DATASET_PATH) as f:
        topics = json.load(f)
    return EvaluationDataset(goldens=[Golden(input=topic) for topic in topics])


def load_topics() -> list[str]:
    with open(_DATASET_PATH) as f:
        return json.load(f)[:1]
