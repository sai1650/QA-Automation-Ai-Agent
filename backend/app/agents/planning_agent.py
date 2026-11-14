from app.agents.base_agent import BaseAgent
from app.ai.prompt_templates import planning_prompt
from app.schemas.qa import RequirementAnalysis, TestingPlan


class PlanningAgent(BaseAgent):
    async def run(self, analysis: RequirementAnalysis) -> TestingPlan:
        plan = await self.generate(
            planning_prompt(analysis.model_dump(mode="json")),
            TestingPlan,
        )
        requirement_ids = {
            requirement.requirement_id
            for requirement in analysis.functional_requirements
        }
        unknown = {
            task.requirement_ref
            for task in plan.tasks
            if task.requirement_ref not in requirement_ids
        }
        if unknown:
            raise ValueError("The testing plan referenced unknown requirements.")
        return plan
