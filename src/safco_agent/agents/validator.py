from __future__ import annotations

from safco_agent.models import ExtractionStatus, ProductRecord


class ValidatorDeduperAgent:
    """Validate product records and remove duplicate variant identities."""

    def dedupe(self, records: list[ProductRecord]) -> list[ProductRecord]:
        unique: dict[str, ProductRecord] = {}
        for record in records:
            unique.setdefault(record.product_id, record)
        return list(unique.values())

    def mark_status(self, record: ProductRecord) -> ProductRecord:
        errors = list(record.errors)
        if not record.parent_product_name:
            errors.append("missing parent_product_name")
        if not record.category_path:
            errors.append("missing category_path")
        status = ExtractionStatus.FAILED if errors else ExtractionStatus.COMPLETE
        return record.model_copy(
            update={
                "errors": errors,
                "extraction_status": status,
            }
        )

