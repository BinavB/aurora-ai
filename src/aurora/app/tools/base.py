"""The tool abstraction every capability implements.

A tool declares typed Pydantic input/output models, descriptive metadata, and
required permissions. :meth:`BaseTool.run` validates raw arguments, enforces
permissions, executes, and always returns a structured :class:`ToolResult` —
never a raw string and never an uncaught exception.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from aurora.app.core.exceptions import (
    AuroraError,
    PermissionDeniedError,
    ValidationError,
)
from aurora.app.core.logging import get_logger
from aurora.app.tools.models import Permission, ToolMetadata, ToolResult


class BaseTool[InputT: BaseModel, OutputT: BaseModel](ABC):
    """Base class for all tools.

    Subclasses set :attr:`metadata`, :attr:`input_model`, :attr:`output_model`
    and implement :meth:`execute`.
    """

    metadata: ToolMetadata
    input_model: type[InputT]
    output_model: type[OutputT]

    def __init__(self) -> None:
        for attr in ("metadata", "input_model", "output_model"):
            if not getattr(self, attr, None):
                raise TypeError(f"{type(self).__name__} must define '{attr}'")
        self._logger = get_logger(f"tools.{self.metadata.name}")

    @property
    def name(self) -> str:
        """The tool's unique name."""
        return self.metadata.name

    def spec(self) -> dict[str, Any]:
        """Return the tool's public schema: metadata plus input/output schemas."""
        return {
            **self.metadata.model_dump(mode="json"),
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(),
        }

    async def run(
        self,
        arguments: dict[str, Any],
        granted: frozenset[Permission] | None = None,
    ) -> ToolResult:
        """Validate, authorize, and execute the tool.

        Args:
            arguments: Raw input to validate against ``input_model``.
            granted: Permissions available to the caller. ``None`` means the
                caller is trusted and all permissions are granted.

        Returns:
            A structured result; failures are captured, never raised.
        """
        try:
            self._authorize(granted)
            payload = self._validate(arguments)
            output = await self.execute(payload)
        except AuroraError as exc:
            self._logger.warning("tool_failed", extra={"code": exc.code})
            return ToolResult(tool=self.name, ok=False, error=exc.to_dict())
        return ToolResult(tool=self.name, ok=True, data=output.model_dump(mode="json"))

    def _authorize(self, granted: frozenset[Permission] | None) -> None:
        if granted is None:
            return
        missing = self.metadata.permissions - granted
        if missing:
            raise PermissionDeniedError(
                f"Tool '{self.name}' requires missing permissions",
                details={"missing": sorted(p.value for p in missing)},
            )

    def _validate(self, arguments: dict[str, Any]) -> InputT:
        try:
            return self.input_model.model_validate(arguments)
        except PydanticValidationError as exc:
            raise ValidationError(
                f"Invalid arguments for tool '{self.name}'",
                details={"errors": exc.errors(include_url=False)},
            ) from exc

    @abstractmethod
    async def execute(self, payload: InputT) -> OutputT:
        """Perform the tool's work. Raise :class:`AuroraError` on failure."""
        raise NotImplementedError
