from datetime import datetime, timezone
from enum import Enum
from typing import Any, List

from pydantic import BaseModel, Field, field_validator


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComplianceIssue(BaseModel):
    id: str = Field(
        ...,
        description="Sequential ID of the non-compliance in the format 'AUD-X' (system normalized).",
    )
    doc_clause_reference: str = Field(
        ...,
        description=(
            "Ultra-specific, exact reference of the violation within the user's contract. "
            "You MUST extract the textual sub-level where the error is located. "
            "Valid examples: 'Clause 2.1', 'Clause 3, Paragraph 2', 'Clause 4, Item b'. "
            "DO NOT accept or return only the macro title (e.g., 'CLAUSE 2')."
        ),
    )
    regulation_violated: str = Field(
        ...,
        description="Article or section of the law/regulation that was violated (e.g., GDPR Art. 7, Item I).",
    )
    risk_level: RiskLevel = Field(
        ...,
        description="Severity level of the risk associated with this legal/regulatory infraction.",
    )
    finding_description: str = Field(
        ...,
        description="Detailed explanation of why this excerpt is not compliant with the regulation.",
    )
    remediation_steps: str = Field(
        ...,
        description="Recommended and practical action to correct the document and mitigate the risk.",
    )

    @field_validator("risk_level", mode="before")
    @classmethod
    def normalize_risk_level(cls, value: Any) -> str:
        """
        Defensive Validator: LLMs parsing foreign-language documents often translate
        requested Enum string values into the document's native language.
        This ensures regional strings/accents map cleanly to the internal English Enum.
        """
        if isinstance(value, str):
            val = value.strip().upper()

            # Mapping common non-English translations/hallucinations to English Enums
            mapping = {
                "BAIXO": "LOW",
                "MÉDIO": "MEDIUM",
                "MEDIO": "MEDIUM",
                "ALTO": "HIGH",
                "CRÍTICO": "CRITICAL",
                "CRITICO": "CRITICAL",
            }
            return mapping.get(val, val)
        return value


class AuditSummary(BaseModel):
    total_issues: int = Field(
        ..., description="Total amount of non-conformities detected."
    )
    critical_risk_count: int = Field(
        ..., description="Total number of CRITICAL level risks."
    )
    high_risk_count: int = Field(..., description="Total number of HIGH level risks.")
    medium_risk_count: int = Field(
        ..., description="Total number of MEDIUM level risks."
    )
    low_risk_count: int = Field(..., description="Total number of LOW level risks.")
    compliance_score: float = Field(
        ..., description="Overall compliance score from 0.0 to 100.0."
    )


class FinalAuditReport(BaseModel):
    document_id: str = Field(..., description="ID of the document that was audited.")
    frameworks_evaluated: List[str] = Field(
        ..., description="List of regulations evaluated."
    )
    audited_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp of when the audit was completed.",
    )
    summary: AuditSummary = Field(
        ..., description="Consolidated statistical summary of the risks found."
    )
    findings: List[ComplianceIssue] = Field(
        ...,
        description="Detailed list of all non-conformities found in the document.",
    )
