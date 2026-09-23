"""Template Execution Pipeline.

Applies a prescriptive TemplateDefinition to a DOCX through the shared
Formatting Operation Layer, producing a lint-validated output.

Public API:

- models:  OperationPlan
- mapper:  build_operation_plan
- runner:  TemplateRunner, run_template, ExecutionResult
"""
from ..models import ExecutionResult
from .mapper import build_operation_plan
from .models import OperationPlan
from .runner import TemplateRunner, run_template

__all__ = [
    "ExecutionResult",
    "OperationPlan",
    "TemplateRunner",
    "build_operation_plan",
    "run_template",
]
