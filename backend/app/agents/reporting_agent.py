from datetime import datetime, timezone
from uuid import UUID

from app.agents.base_agent import BaseAgent
from app.ai.prompt_templates import reporting_prompt
from app.schemas.qa import (
    BugFinding,
    ExecutionResult,
    GeneratedTestCase,
    QAReport,
    ReportFact,
    ReportNarrative,
    TestOutcome,
    HistoricalBugMatch,
)


class ReportingAgent(BaseAgent):
    async def run(
        self,
        execution_id: UUID,
        tests: list[GeneratedTestCase],
        results: list[ExecutionResult],
        findings: list[BugFinding],
        observed_facts: list[ReportFact],
        *,
        rag_status: str = "not_needed",
        historical_bug_matches: list[HistoricalBugMatch] | None = None,
    ) -> QAReport:
        narrative = await self.generate(
            reporting_prompt(
                [item.model_dump(mode="json") for item in results],
                [item.model_dump(mode="json") for item in findings],
                [item.model_dump(mode="json") for item in observed_facts],
            ),
            ReportNarrative,
        )
        counts = {outcome: 0 for outcome in TestOutcome}
        for result in results:
            counts[result.status] += 1
        ai_analysis = [
            f"{finding.title}: {finding.probable_root_cause}"
            for finding in findings
        ]
        return QAReport(
            execution_id=execution_id,
            generated_at=datetime.now(timezone.utc),
            summary=narrative.summary,
            status_counts=counts,
            tests=tests,
            execution_results=results,
            findings=findings,
            observed_facts=observed_facts,
            ai_analysis=ai_analysis,
            recommendations=narrative.recommendations,
            rag_status=rag_status,
            historical_bug_matches=historical_bug_matches or [],
        )
