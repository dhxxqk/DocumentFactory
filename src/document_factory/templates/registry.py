"""Template Registry: in-memory index of TemplateDefinitions.

The Registry is the lookup point between a template id (``GRID_TECH_V1_4``)
and the prescriptive TemplateDefinition. Callers (formatting runner, CLI,
future agents) ask the Registry for a template by id and never inspect the
``templates/`` directory themselves.

Exceptions reuse ``DocumentFactoryError`` so they surface through the same
user-readable error channel as the rest of DocumentFactory.
"""
from __future__ import annotations

from ..models import DocumentFactoryError
from .schema import TemplateDefinition, TemplateSummary


class TemplateNotFoundError(DocumentFactoryError):
    """Raised when a template id is not registered."""


class TemplateAlreadyRegisteredError(DocumentFactoryError):
    """Raised when a template id is registered twice."""


class TemplateRegistry:
    """In-memory index of TemplateDefinitions."""

    def __init__(self):
        self._templates: dict[str, TemplateDefinition] = {}

    def register_template(self, definition: TemplateDefinition) -> None:
        """Register a template. Raises if the id already exists."""
        if not isinstance(definition, TemplateDefinition):
            raise DocumentFactoryError(
                "register_template 需要 TemplateDefinition 实例"
            )
        if definition.id in self._templates:
            raise TemplateAlreadyRegisteredError(definition.id)
        self._templates[definition.id] = definition

    def get_template(self, template_id: str) -> TemplateDefinition:
        """Return the template for id. Raises TemplateNotFoundError if absent."""
        try:
            return self._templates[template_id]
        except KeyError:
            raise TemplateNotFoundError(template_id) from None

    def list_templates(self) -> list[TemplateSummary]:
        """Return summaries of all registered templates, sorted by id."""
        return [
            TemplateSummary.from_definition(self._templates[key])
            for key in sorted(self._templates)
        ]

    def has_template(self, template_id: str) -> bool:
        """Return whether a template id is registered."""
        return template_id in self._templates
