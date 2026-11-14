from app.agents.base_agent import BaseAgent
from app.ai.prompt_templates import requirement_prompt
from app.schemas.qa import RequirementAnalysis


class RequirementAnalysisAgent(BaseAgent):
    async def run(self, requirements: str) -> RequirementAnalysis:
        return await self.generate(
            requirement_prompt(requirements),
            RequirementAnalysis,
        )
