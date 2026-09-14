"""Shared response envelopes: pagination, errors, pagination params."""

from __future__ import annotations

from typing import Annotated, Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ErrorDetail(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["AI system not found."])
    details: Any = None
    correlation_id: str | None = Field(default=None, examples=["6f1c1f0e-..."])


class ErrorResponse(BaseModel):
    error: ErrorDetail

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "not_found",
                    "message": "AI system not found.",
                    "details": None,
                    "correlation_id": "0f4b9a2e-6c2b-4f0e-9a4a-1c2b3d4e5f60",
                }
            }
        }
    )


class PageMeta(BaseModel):
    total: int = Field(examples=[137])
    page: int = Field(examples=[1])
    page_size: int = Field(examples=[25])
    pages: int = Field(examples=[6])


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = settings.DEFAULT_PAGE_SIZE
    sort_by: str | None = None
    sort_dir: str = "desc"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: Annotated[int, Query(ge=1, description="1-indexed page number")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=settings.MAX_PAGE_SIZE, description="Items per page")
    ] = settings.DEFAULT_PAGE_SIZE,
    sort_by: Annotated[str | None, Query(description="Field to sort by")] = None,
    sort_dir: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size, sort_by=sort_by, sort_dir=sort_dir)


def build_page(items: list[Any], total: int, params: PaginationParams) -> dict[str, Any]:
    pages = (total + params.page_size - 1) // params.page_size if params.page_size else 0
    return {
        "items": items,
        "meta": {
            "total": total,
            "page": params.page,
            "page_size": params.page_size,
            "pages": pages,
        },
    }
