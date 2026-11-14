from typing import Any

from app.agents.base_agent import BaseAgent
from app.ai.prompt_templates import build_test_generation_prompt
from app.schemas.qa import (
    RequirementAnalysis,
    TestCaseSet,
    TestingPlan,
    WebsiteUnderstanding,
)


class TestGenerationAgent(BaseAgent):
    async def run(
        self,
        analysis: RequirementAnalysis,
        plan: TestingPlan,
        understanding: WebsiteUnderstanding,
        evidence_index: dict[str, Any],
    ) -> TestCaseSet:
        generated = await self.generate(
            build_test_generation_prompt(
                analysis.model_dump(mode="json"),
                plan.model_dump(mode="json"),
                understanding.model_dump(mode="json"),
                evidence_index,
            ),
            TestCaseSet,
        )
        requirement_ids = {
            requirement.requirement_id
            for requirement in analysis.functional_requirements
        }
        planned_requirements = {task.requirement_ref for task in plan.tasks}
        allowed_evidence = set(evidence_index)

        def _normalize(ref: str) -> str:
            if ref in allowed_evidence:
                return ref
            if "." in ref and ref.rsplit(".", 1)[0] in allowed_evidence:
                return ref.rsplit(".", 1)[0]
            return ref

        for case in generated.test_cases:
            case.evidence_requirements = [
                _normalize(r) for r in case.evidence_requirements
            ]
        if any(
            case.requirement_id not in requirement_ids
            or case.requirement_id not in planned_requirements
            for case in generated.test_cases
        ):
            raise ValueError(
                "Generated test cases referenced requirements absent from the plan."
            )
        for case in generated.test_cases:
            if not set(case.evidence_requirements) <= allowed_evidence:
                raise ValueError(
                    "Generated test cases cited evidence that was not observed."
                )
            criteria = case.validation_criteria
            if criteria.kind.value == "PAGE_LOAD" and (
                "page.navigation_status" not in case.evidence_requirements
            ):
                raise ValueError(
                    "Page-load tests must cite observed navigation status."
                )
            if criteria.kind.value == "ELEMENT_COUNT" and criteria.element_kind:
                key = {
                    "BUTTON": "buttons",
                    "LINK": "links",
                    "INPUT": "inputs",
                    "SELECT": "selects",
                    "TEXTAREA": "textareas",
                    "FORM": "forms",
                }[criteria.element_kind.value]
                if f"elements.{key}.count" not in case.evidence_requirements:
                    raise ValueError(
                        "Element tests must cite the matching observed count."
                    )
        return generated
