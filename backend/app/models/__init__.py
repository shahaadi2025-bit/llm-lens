"""Import every model so Base.metadata is complete for Alembic and create_all."""
from app.models.analysis import FailureCluster, FailureMode, Report
from app.models.base import Base
from app.models.experiment import Experiment, ExperimentConfig, ExperimentLineage, ExperimentRun, Prompt
from app.models.model_registry import LLMModel, ModelVersion
from app.models.notebook import Investigation, InvestigationExperiment, InvestigationNote
from app.models.result import Evaluation, Metric, MetricEvidence, Response
from app.models.user import User

__all__ = [
    "Base", "User", "LLMModel", "ModelVersion", "Experiment", "ExperimentConfig", "ExperimentLineage",
    "ExperimentRun", "Prompt", "Response", "Evaluation", "Metric", "MetricEvidence",
    "FailureMode", "FailureCluster", "Report", "Investigation", "InvestigationExperiment", "InvestigationNote",
]
