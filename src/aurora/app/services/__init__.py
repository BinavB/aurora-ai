"""Services layer: coordinate business logic.

Services sit between the API and the agents: ``API → Services → Agents →
Tools → Providers``. They wire the router, provider factory, context engine,
memory, and agents into cohesive use cases, and contain no low-level logic.
"""

from aurora.app.services.agent_pipeline import AgentPipeline
from aurora.app.services.autonomous_service import AutonomousService
from aurora.app.services.chat_service import ChatService
from aurora.app.services.collaboration_service import (
    CollaborationService,
    CollabResult,
    Effort,
)
from aurora.app.services.execution_service import ExecutionService
from aurora.app.services.factory import DefaultProviderFactory, ProviderFactory
from aurora.app.services.implementation_service import ImplementationService
from aurora.app.services.memory_service import MemoryService
from aurora.app.services.models import (
    AgentResult,
    ChatReply,
    ImplementResult,
    MemoryReceipt,
    PipelineResult,
    PlanResult,
    ReviewOutcome,
    TaskSpec,
    VerificationReport,
)
from aurora.app.services.planning_service import PlanningService
from aurora.app.services.review_service import ReviewService
from aurora.app.services.task_service import TaskService
from aurora.app.services.transcription_service import TranscriptionService
from aurora.app.services.verification_service import VerificationService

__all__ = [
    "ProviderFactory",
    "DefaultProviderFactory",
    "ChatService",
    "PlanningService",
    "ReviewService",
    "ImplementationService",
    "TranscriptionService",
    "CollaborationService",
    "CollabResult",
    "Effort",
    "AutonomousService",
    "TaskService",
    "ExecutionService",
    "VerificationService",
    "MemoryService",
    "AgentPipeline",
    "ChatReply",
    "PlanResult",
    "ReviewOutcome",
    "ImplementResult",
    "AgentResult",
    "TaskSpec",
    "VerificationReport",
    "MemoryReceipt",
    "PipelineResult",
]
