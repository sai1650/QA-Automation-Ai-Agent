from typing import Any

from app.agents.base_agent import BaseAgent
from app.ai.prompt_templates import bug_analysis_prompt
from app.schemas.qa import BugFindingSet


class BugAnalysisAgent(BaseAgent):
    async def run(
        self,
        execution_results: list[dict[str, Any]],
        evidence_index: dict[str, Any],
        historical_context: str = "",
        historical_references: set[str] | None = None,
    ) -> BugFindingSet:
        finding_set = await self.generate(
            bug_analysis_prompt(
                execution_results,
                evidence_index,
                historical_context,
                historical_references,
            ),
            BugFindingSet,
        )
        allowed_evidence = set(evidence_index)
        allowed_historical_references = historical_references or set()

        def _normalize(ref: str) -> str:
            if ref in allowed_evidence:
                return ref
            if "." in ref and ref.rsplit(".", 1)[0] in allowed_evidence:
                return ref.rsplit(".", 1)[0]
            return ref

        for finding in finding_set.findings:
            finding.supporting_evidence = [
                _normalize(r) for r in finding.supporting_evidence
            ]
            if not set(finding.supporting_evidence) <= allowed_evidence:
                raise ValueError(
                    "Bug analysis cited evidence that was not observed."
                )
            if finding.affected_url not in {
                evidence_index.get("page.final_url"),
                evidence_index.get("page.requested_url"),
                None,
            }:
                raise ValueError(
                    "Bug analysis cited a URL that was not inspected."
                )
            if not set(finding.historical_references) <= allowed_historical_references:
                raise ValueError(
                    "Bug analysis cited unavailable historical knowledge."
                )
        return finding_set
