"""Generic Documentation Engine foundation."""

from .builders import BuildContext, BuildEngine, BuildOperation, BuilderRegistry, DerivedObject
from .dependencies import ComparatorRegistry, DependencyRuntime, ExplicitDependency
from .materialization import MaterializationRuntime, RendererRegistry, SyncRuntime
from .semantic import SemanticDependencyRegistry, SemanticReviewRuntime, ValidationContext
from .verification import VerificationRuntime
from .hardening import HardeningManager, MigrationManager
from .versions import ENGINE_VERSION, MACHINE_OUTPUT_SCHEMA_VERSION, PERSISTED_STATE_SCHEMA_VERSION, RUNTIME_LAYOUT_VERSION

__all__ = [
    "BuildContext",
    "BuildEngine",
    "BuildOperation",
    "BuilderRegistry",
    "DerivedObject",
    "ComparatorRegistry",
    "DependencyRuntime",
    "ExplicitDependency",
    "MaterializationRuntime",
    "RendererRegistry",
    "SyncRuntime",
    "SemanticDependencyRegistry",
    "SemanticReviewRuntime",
    "ValidationContext",
    "VerificationRuntime",
    "HardeningManager",
    "MigrationManager",
    "ENGINE_VERSION",
    "MACHINE_OUTPUT_SCHEMA_VERSION",
    "PERSISTED_STATE_SCHEMA_VERSION",
    "RUNTIME_LAYOUT_VERSION",
]
