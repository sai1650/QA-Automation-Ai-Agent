from typing import Any

from app.agents.base_agent import BaseAgent
from app.ai.prompt_templates import website_prompt
from app.schemas.qa import RequirementAnalysis, WebsiteUnderstanding


class WebsiteUnderstandingAgent(BaseAgent):
    async def run(
        self,
        analysis: RequirementAnalysis,
        evidence_index: dict[str, Any],
    ) -> WebsiteUnderstanding:
        understanding = await self.generate(
            website_prompt(
                analysis.model_dump(mode="json"),
                evidence_index,
            ),
            WebsiteUnderstanding,
        )
        valid_requirement_ids = {
            requirement.requirement_id
            for requirement in analysis.functional_requirements
        }
        allowed_evidence = set(evidence_index)

        def _normalize(ref: str) -> str:
            if ref in allowed_evidence:
                return ref
            if "." in ref and ref.rsplit(".", 1)[0] in allowed_evidence:
                return ref.rsplit(".", 1)[0]
            return ref

        for item in understanding.requirement_evidence:
            item.evidence_references = [
                _normalize(r) for r in item.evidence_references
            ]
        understanding.observed_element_references = [
            _normalize(r) for r in understanding.observed_element_references
        ]

        if any(
            item.requirement_id not in valid_requirement_ids
            for item in understanding.requirement_evidence
        ):
            raise ValueError(
                "Website analysis referenced an unknown requirement."
            )
        mapped_ids = [
            item.requirement_id for item in understanding.requirement_evidence
        ]
        if set(mapped_ids) != valid_requirement_ids or len(mapped_ids) != len(
            valid_requirement_ids
        ):
            raise ValueError(
                "Website analysis must map each requirement exactly once."
            )
        referenced = {
            reference
            for item in understanding.requirement_evidence
            for reference in item.evidence_references
        } | set(understanding.observed_element_references)
        if not referenced <= allowed_evidence:
            raise ValueError(
                "Website analysis cited evidence that was not observed."
            )
        if any(
            not reference.startswith("elements.")
            for reference in understanding.observed_element_references
        ):
            raise ValueError(
                "Website analysis cited a non-element as an observed element."
            )
        return understanding
