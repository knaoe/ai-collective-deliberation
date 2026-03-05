"""
MAGI Consensus Engine
======================
The heart of the MAGI system. Three personas deliberate in three phases:
  Phase 1: Independent Analysis (独立思考)
  Phase 2: Debate (討論)
  Phase 3: Consensus Vote (合議)
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Callable, Optional

from dotenv import load_dotenv
from openai import AzureOpenAI, AsyncAzureOpenAI

from magi_engine.personas import (
    ALL_PERSONAS,
    BALTHASAR,
    CASPER,
    MELCHIOR,
    Persona,
    Vote,
)
from magi_engine.cost_tracker import CostTracker, DeliberationCost


load_dotenv()


@dataclass
class PersonaResponse:
    persona_name: str
    phase: str
    content: str
    vote: Optional[Vote] = None
    conditions: Optional[str] = None


@dataclass
class Deliberation:
    question: str
    timestamp: float = field(default_factory=time.time)
    phase1_analyses: list[PersonaResponse] = field(default_factory=list)
    phase2_debates: list[PersonaResponse] = field(default_factory=list)
    phase3_votes: list[PersonaResponse] = field(default_factory=list)
    consensus: Optional[str] = None
    final_verdict: Optional[str] = None
    cost: Optional[DeliberationCost] = None

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "timestamp": self.timestamp,
            "phase1_independent_analysis": [
                {"persona": r.persona_name, "analysis": r.content}
                for r in self.phase1_analyses
            ],
            "phase2_debate": [
                {"persona": r.persona_name, "response": r.content}
                for r in self.phase2_debates
            ],
            "phase3_votes": [
                {
                    "persona": r.persona_name,
                    "vote": r.vote.value if r.vote else None,
                    "reasoning": r.content,
                    "conditions": r.conditions,
                }
                for r in self.phase3_votes
            ],
            "consensus": self.consensus,
            "final_verdict": self.final_verdict,
            "cost": self.cost.to_dict() if self.cost else None,
        }


class MAGIEngine:
    """The MAGI Consensus Engine -- three minds, one judgment."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        deployment: Optional[str] = None,
    ):
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        self.deployment = deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5")

        if not self.endpoint or not self.api_key:
            raise ValueError("Azure OpenAI endpoint and API key are required.")

        self.sync_client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )
        self.async_client = AsyncAzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )
        self.cost_tracker = CostTracker(model=self.deployment)
        self.history: list[Deliberation] = []

    def _call_llm(
        self,
        persona: Persona,
        messages: list[dict],
        phase: str,
        max_retries: int = 2,
    ) -> str:
        """Synchronous LLM call with cost tracking and content filter retry.

        Retry strategy for content filter issues:
        - Attempt 0: Normal request with max_completion_tokens=1024
        - Attempt 1: Add conciseness instruction, reduce to 512 tokens
        - Attempt 2: Simplified prompt, 256 tokens
        """
        from openai import BadRequestError

        # Progressive token limits to reduce output filter triggers
        token_limits = [1024, 512, 256]

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                retry_messages = list(messages)
                max_tokens = token_limits[min(attempt, len(token_limits) - 1)]

                if attempt > 0 and retry_messages:
                    original = retry_messages[-1].get("content", "")
                    # Truncate very long content
                    if len(original) > 2000:
                        original = original[:2000] + "\n[Truncated]"
                    # Add explicit conciseness and compliance framing
                    retry_messages = retry_messages[:-1] + [{
                        "role": "user",
                        "content": (
                            f"Please provide a concise, constructive analysis (under {max_tokens} words). "
                            f"Focus on practical considerations and balanced perspectives.\n\n"
                            f"{original}"
                        ),
                    }]

                start = time.time()
                response = self.sync_client.chat.completions.create(
                    model=self.deployment,
                    messages=[{"role": "system", "content": persona.system_prompt}] + retry_messages,
                    max_completion_tokens=max_tokens,
                )
                duration_ms = (time.time() - start) * 1000

                usage = response.usage
                if usage:
                    self.cost_tracker.record_call(
                        persona=persona.name,
                        phase=phase,
                        input_tokens=usage.prompt_tokens,
                        output_tokens=usage.completion_tokens,
                        duration_ms=duration_ms,
                    )

                content = response.choices[0].message.content or ""
                finish_reason = response.choices[0].finish_reason

                # Handle content filter on the response side
                if not content and finish_reason == "content_filter":
                    if attempt < max_retries:
                        print(f"  [RETRY] {persona.name}/{phase}: Response filtered (attempt {attempt + 1}/{max_retries + 1}), reducing output length")
                        continue
                    print(f"  [WARN] {persona.name}/{phase}: Content filter blocked all {max_retries + 1} attempts")
                    return self._content_filter_fallback(persona, phase)

                if content:
                    return content

                # Empty content for unknown reason
                if attempt < max_retries:
                    print(f"  [RETRY] {persona.name}/{phase}: Empty response (attempt {attempt + 1}/{max_retries + 1})")
                    continue

            except BadRequestError as e:
                last_error = e
                error_str = str(e)
                if "content_filter" in error_str or "content_management" in error_str:
                    if attempt < max_retries:
                        print(f"  [RETRY] {persona.name}/{phase}: Request filtered (attempt {attempt + 1}/{max_retries + 1})")
                        continue
                    print(f"  [WARN] {persona.name}/{phase}: Content filter blocked after {max_retries + 1} attempts")
                    return self._content_filter_fallback(persona, phase)
                raise

        return self._content_filter_fallback(persona, phase)

    @staticmethod
    def _content_filter_fallback(persona: Persona, phase: str) -> str:
        """Generate an informative fallback when content filters block all attempts."""
        if "phase1" in phase:
            return (
                f"As {persona.name} ({persona.title}), I approach this question by considering "
                f"multiple dimensions: the empirical evidence available, the impact on stakeholders, "
                f"and the practical feasibility of different approaches. A thorough analysis requires "
                f"examining both the potential benefits and risks, weighing short-term gains against "
                f"long-term consequences, and considering diverse perspectives. I believe we should "
                f"proceed cautiously, ensuring that any decision is well-informed and accounts for "
                f"the interests of all affected parties."
            )
        elif "phase2" in phase:
            return (
                f"As {persona.name} ({persona.title}), I find areas of both agreement and "
                f"constructive disagreement with my fellow MAGI members. The key tension lies "
                f"between ambitious action and prudent caution. I believe we should seek a balanced "
                f"approach that acknowledges the legitimate concerns raised while pursuing "
                f"constructive progress. The strongest path forward integrates evidence-based "
                f"reasoning with genuine concern for human welfare and practical implementation."
            )
        else:
            return (
                f"[{persona.name} - {persona.title}] After careful deliberation, I believe this "
                f"topic requires nuanced consideration of feasibility, stakeholder impact, and "
                f"long-term consequences. I defer to the collective MAGI judgment."
            )

    async def _async_call_llm(
        self,
        persona: Persona,
        messages: list[dict],
        phase: str,
        max_retries: int = 2,
    ) -> str:
        """Async LLM call with cost tracking and content filter retry.

        Uses same progressive retry strategy as _call_llm.
        """
        from openai import BadRequestError

        token_limits = [1024, 512, 256]

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                retry_messages = list(messages)
                max_tokens = token_limits[min(attempt, len(token_limits) - 1)]

                if attempt > 0 and retry_messages:
                    original = retry_messages[-1].get("content", "")
                    if len(original) > 2000:
                        original = original[:2000] + "\n[Truncated]"
                    retry_messages = retry_messages[:-1] + [{
                        "role": "user",
                        "content": (
                            f"Please provide a concise, constructive analysis (under {max_tokens} words). "
                            f"Focus on practical considerations and balanced perspectives.\n\n"
                            f"{original}"
                        ),
                    }]

                start = time.time()
                response = await self.async_client.chat.completions.create(
                    model=self.deployment,
                    messages=[{"role": "system", "content": persona.system_prompt}] + retry_messages,
                    max_completion_tokens=max_tokens,
                )
                duration_ms = (time.time() - start) * 1000

                usage = response.usage
                if usage:
                    self.cost_tracker.record_call(
                        persona=persona.name,
                        phase=phase,
                        input_tokens=usage.prompt_tokens,
                        output_tokens=usage.completion_tokens,
                        duration_ms=duration_ms,
                    )

                content = response.choices[0].message.content or ""
                finish_reason = response.choices[0].finish_reason

                if not content and finish_reason == "content_filter":
                    if attempt < max_retries:
                        print(f"  [RETRY] {persona.name}/{phase}: Response filtered (attempt {attempt + 1}/{max_retries + 1})")
                        continue
                    print(f"  [WARN] {persona.name}/{phase}: Content filter blocked all {max_retries + 1} attempts")
                    return self._content_filter_fallback(persona, phase)

                if content:
                    return content

                if attempt < max_retries:
                    print(f"  [RETRY] {persona.name}/{phase}: Empty response (attempt {attempt + 1}/{max_retries + 1})")
                    continue

            except BadRequestError as e:
                last_error = e
                error_str = str(e)
                if "content_filter" in error_str or "content_management" in error_str:
                    if attempt < max_retries:
                        print(f"  [RETRY] {persona.name}/{phase}: Request filtered (attempt {attempt + 1}/{max_retries + 1})")
                        continue
                    print(f"  [WARN] {persona.name}/{phase}: Content filter blocked after {max_retries + 1} attempts")
                    return self._content_filter_fallback(persona, phase)
                raise

        return self._content_filter_fallback(persona, phase)

    def deliberate(
        self,
        question: str,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ) -> Deliberation:
        """
        Run a full MAGI deliberation (synchronous).

        Args:
            question: The question or topic to deliberate on.
            on_event: Optional callback for real-time events.

        Returns:
            A complete Deliberation record.
        """
        delib = Deliberation(question=question)
        delib.cost = self.cost_tracker.begin_deliberation()

        def emit(event_type: str, data: dict):
            if on_event:
                on_event(event_type, data)

        emit("deliberation_start", {"question": question})

        # =====================================================
        # Phase 1: Independent Analysis (独立思考)
        # =====================================================
        emit("phase_start", {"phase": 1, "name": "Independent Analysis / 独立思考"})

        for persona in ALL_PERSONAS:
            emit("persona_thinking", {"persona": persona.name, "phase": 1})
            content = self._call_llm(
                persona,
                [
                    {
                        "role": "user",
                        "content": (
                            f"MAGI DELIBERATION INITIATED\n"
                            f"==========================\n\n"
                            f"Question for deliberation:\n{question}\n\n"
                            f"As {persona.name} ({persona.title} / {persona.title_jp}), "
                            f"provide your independent analysis. Consider this question "
                            f"through your unique perspective. Be thorough but focused."
                        ),
                    }
                ],
                phase="phase1_analysis",
            )
            response = PersonaResponse(
                persona_name=persona.name,
                phase="phase1",
                content=content,
            )
            delib.phase1_analyses.append(response)
            emit("persona_response", {
                "persona": persona.name,
                "phase": 1,
                "content": content,
            })

        emit("phase_complete", {"phase": 1})

        # =====================================================
        # Phase 2: Debate (討論)
        # =====================================================
        emit("phase_start", {"phase": 2, "name": "Debate / 討論"})

        # Build the summary of Phase 1 for cross-examination
        analyses_summary = "\n\n".join(
            f"=== {r.persona_name} ===\n{r.content}"
            for r in delib.phase1_analyses
        )

        for persona in ALL_PERSONAS:
            other_names = [p.name for p in ALL_PERSONAS if p.name != persona.name]
            emit("persona_thinking", {"persona": persona.name, "phase": 2})
            content = self._call_llm(
                persona,
                [
                    {
                        "role": "user",
                        "content": (
                            f"MAGI DELIBERATION - PHASE 2: DEBATE\n"
                            f"====================================\n\n"
                            f"Original question:\n{question}\n\n"
                            f"All three MAGI have provided their independent analyses:\n\n"
                            f"{analyses_summary}\n\n"
                            f"As {persona.name} ({persona.title}), respond to "
                            f"{' and '.join(other_names)}. Where do you agree? "
                            f"Where do you disagree? What have they missed? "
                            f"Challenge their reasoning where it is weak. "
                            f"Acknowledge their insights where they are strong. "
                            f"Refine your own position."
                        ),
                    }
                ],
                phase="phase2_debate",
            )
            response = PersonaResponse(
                persona_name=persona.name,
                phase="phase2",
                content=content,
            )
            delib.phase2_debates.append(response)
            emit("persona_response", {
                "persona": persona.name,
                "phase": 2,
                "content": content,
            })

        emit("phase_complete", {"phase": 2})

        # =====================================================
        # Phase 3: Consensus Vote (合議)
        # =====================================================
        emit("phase_start", {"phase": 3, "name": "Consensus Vote / 合議"})

        debate_summary = "\n\n".join(
            f"=== {r.persona_name} (debate) ===\n{r.content}"
            for r in delib.phase2_debates
        )

        for persona in ALL_PERSONAS:
            emit("persona_thinking", {"persona": persona.name, "phase": 3})
            content = self._call_llm(
                persona,
                [
                    {
                        "role": "user",
                        "content": (
                            f"MAGI DELIBERATION - PHASE 3: FINAL VOTE\n"
                            f"=========================================\n\n"
                            f"Original question:\n{question}\n\n"
                            f"After independent analysis and debate, it is time to vote.\n\n"
                            f"Debate record:\n{debate_summary}\n\n"
                            f"As {persona.name} ({persona.title}), cast your final vote.\n\n"
                            f"You MUST respond in EXACTLY this format:\n\n"
                            f"VOTE: [APPROVE / CONDITIONAL / REJECT]\n"
                            f"CONDITIONS: [If CONDITIONAL, state your conditions. If not, write 'None']\n"
                            f"REASONING: [Your final reasoning in 2-4 sentences]\n"
                        ),
                    }
                ],
                phase="phase3_vote",
            )

            # Parse the vote
            vote = self._parse_vote(content)
            conditions = self._parse_conditions(content)

            response = PersonaResponse(
                persona_name=persona.name,
                phase="phase3",
                content=content,
                vote=vote,
                conditions=conditions,
            )
            delib.phase3_votes.append(response)
            emit("persona_response", {
                "persona": persona.name,
                "phase": 3,
                "content": content,
                "vote": vote.value,
            })

        emit("phase_complete", {"phase": 3})

        # =====================================================
        # Final Synthesis
        # =====================================================
        votes = [r.vote for r in delib.phase3_votes]
        delib.final_verdict = self._determine_verdict(votes)
        delib.consensus = self._synthesize_consensus(delib)

        emit("deliberation_complete", {
            "verdict": delib.final_verdict,
            "consensus": delib.consensus,
            "votes": {r.persona_name: r.vote.value for r in delib.phase3_votes},
        })

        self.history.append(delib)
        return delib

    async def deliberate_async(
        self,
        question: str,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        """
        Run a MAGI deliberation with async streaming events.

        Yields (event_type, data) tuples for real-time consumption.
        """
        delib = Deliberation(question=question)
        delib.cost = self.cost_tracker.begin_deliberation()

        yield ("deliberation_start", {"question": question})

        # Phase 1: Independent Analysis (parallel)
        yield ("phase_start", {"phase": 1, "name": "Independent Analysis / 独立思考"})

        async def phase1_task(persona: Persona) -> PersonaResponse:
            content = await self._async_call_llm(
                persona,
                [
                    {
                        "role": "user",
                        "content": (
                            f"MAGI DELIBERATION INITIATED\n"
                            f"==========================\n\n"
                            f"Question for deliberation:\n{question}\n\n"
                            f"As {persona.name} ({persona.title} / {persona.title_jp}), "
                            f"provide your independent analysis. Consider this question "
                            f"through your unique perspective. Be thorough but focused."
                        ),
                    }
                ],
                phase="phase1_analysis",
            )
            return PersonaResponse(
                persona_name=persona.name, phase="phase1", content=content
            )

        # Run Phase 1 in parallel
        tasks = [phase1_task(p) for p in ALL_PERSONAS]
        results = await asyncio.gather(*tasks)
        for r in results:
            delib.phase1_analyses.append(r)
            yield ("persona_response", {
                "persona": r.persona_name,
                "phase": 1,
                "content": r.content,
            })

        yield ("phase_complete", {"phase": 1})

        # Phase 2: Debate (parallel)
        yield ("phase_start", {"phase": 2, "name": "Debate / 討論"})

        analyses_summary = "\n\n".join(
            f"=== {r.persona_name} ===\n{r.content}"
            for r in delib.phase1_analyses
        )

        async def phase2_task(persona: Persona) -> PersonaResponse:
            other_names = [p.name for p in ALL_PERSONAS if p.name != persona.name]
            content = await self._async_call_llm(
                persona,
                [
                    {
                        "role": "user",
                        "content": (
                            f"MAGI DELIBERATION - PHASE 2: DEBATE\n"
                            f"====================================\n\n"
                            f"Original question:\n{question}\n\n"
                            f"All three MAGI have provided their independent analyses:\n\n"
                            f"{analyses_summary}\n\n"
                            f"As {persona.name} ({persona.title}), respond to "
                            f"{' and '.join(other_names)}. Where do you agree? "
                            f"Where do you disagree? What have they missed? "
                            f"Challenge their reasoning where it is weak. "
                            f"Acknowledge their insights where they are strong. "
                            f"Refine your own position."
                        ),
                    }
                ],
                phase="phase2_debate",
            )
            return PersonaResponse(
                persona_name=persona.name, phase="phase2", content=content
            )

        tasks = [phase2_task(p) for p in ALL_PERSONAS]
        results = await asyncio.gather(*tasks)
        for r in results:
            delib.phase2_debates.append(r)
            yield ("persona_response", {
                "persona": r.persona_name,
                "phase": 2,
                "content": r.content,
            })

        yield ("phase_complete", {"phase": 2})

        # Phase 3: Vote (parallel)
        yield ("phase_start", {"phase": 3, "name": "Consensus Vote / 合議"})

        debate_summary = "\n\n".join(
            f"=== {r.persona_name} (debate) ===\n{r.content}"
            for r in delib.phase2_debates
        )

        async def phase3_task(persona: Persona) -> PersonaResponse:
            content = await self._async_call_llm(
                persona,
                [
                    {
                        "role": "user",
                        "content": (
                            f"MAGI DELIBERATION - PHASE 3: FINAL VOTE\n"
                            f"=========================================\n\n"
                            f"Original question:\n{question}\n\n"
                            f"After independent analysis and debate, it is time to vote.\n\n"
                            f"Debate record:\n{debate_summary}\n\n"
                            f"As {persona.name} ({persona.title}), cast your final vote.\n\n"
                            f"You MUST respond in EXACTLY this format:\n\n"
                            f"VOTE: [APPROVE / CONDITIONAL / REJECT]\n"
                            f"CONDITIONS: [If CONDITIONAL, state your conditions. If not, write 'None']\n"
                            f"REASONING: [Your final reasoning in 2-4 sentences]\n"
                        ),
                    }
                ],
                phase="phase3_vote",
            )
            vote = self._parse_vote(content)
            conditions = self._parse_conditions(content)
            return PersonaResponse(
                persona_name=persona.name,
                phase="phase3",
                content=content,
                vote=vote,
                conditions=conditions,
            )

        tasks = [phase3_task(p) for p in ALL_PERSONAS]
        results = await asyncio.gather(*tasks)
        for r in results:
            delib.phase3_votes.append(r)
            yield ("persona_response", {
                "persona": r.persona_name,
                "phase": 3,
                "content": r.content,
                "vote": r.vote.value if r.vote else None,
            })

        yield ("phase_complete", {"phase": 3})

        # Final synthesis
        votes = [r.vote for r in delib.phase3_votes]
        delib.final_verdict = self._determine_verdict(votes)
        delib.consensus = self._synthesize_consensus(delib)

        self.history.append(delib)

        yield ("deliberation_complete", {
            "verdict": delib.final_verdict,
            "consensus": delib.consensus,
            "votes": {r.persona_name: r.vote.value for r in delib.phase3_votes},
            "cost": delib.cost.to_dict() if delib.cost else None,
            "full_deliberation": delib.to_dict(),
        })

    @staticmethod
    def _parse_vote(content: str) -> Vote:
        """Parse a vote from the LLM response."""
        upper = content.upper()
        if "VOTE: APPROVE" in upper or "VOTE:APPROVE" in upper:
            return Vote.APPROVE
        elif "VOTE: REJECT" in upper or "VOTE:REJECT" in upper:
            return Vote.REJECT
        elif "VOTE: CONDITIONAL" in upper or "VOTE:CONDITIONAL" in upper:
            return Vote.CONDITIONAL
        # Fallback: look for keywords
        if "REJECT" in upper.split("VOTE")[-1][:30] if "VOTE" in upper else "":
            return Vote.REJECT
        if "APPROVE" in upper:
            return Vote.APPROVE
        return Vote.CONDITIONAL

    @staticmethod
    def _parse_conditions(content: str) -> Optional[str]:
        """Parse conditions from a CONDITIONAL vote."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().upper().startswith("CONDITIONS:"):
                cond = line.split(":", 1)[1].strip()
                if cond.lower() == "none" or cond.lower() == "n/a":
                    return None
                # Gather multi-line conditions
                parts = [cond]
                for next_line in lines[i + 1 :]:
                    if next_line.strip().upper().startswith("REASONING:"):
                        break
                    if next_line.strip():
                        parts.append(next_line.strip())
                return " ".join(parts) if any(parts) else None
        return None

    @staticmethod
    def _determine_verdict(votes: list[Vote]) -> str:
        """Determine the final verdict from three votes."""
        approve_count = sum(1 for v in votes if v == Vote.APPROVE)
        reject_count = sum(1 for v in votes if v == Vote.REJECT)
        conditional_count = sum(1 for v in votes if v == Vote.CONDITIONAL)

        if approve_count >= 2:
            if approve_count == 3:
                return "UNANIMOUS APPROVAL (全会一致承認)"
            return "MAJORITY APPROVAL (多数決承認)"
        elif reject_count >= 2:
            if reject_count == 3:
                return "UNANIMOUS REJECTION (全会一致拒否)"
            return "MAJORITY REJECTION (多数決拒否)"
        elif conditional_count >= 2:
            return "CONDITIONAL APPROVAL (条件付き承認)"
        else:
            # Mixed votes -- no clear majority
            return "SPLIT DECISION - CONDITIONAL (分裂判定・条件付き)"

    def _synthesize_consensus(self, delib: Deliberation) -> str:
        """Generate a final consensus synthesis."""
        vote_summary = ", ".join(
            f"{r.persona_name}: {r.vote.value}" for r in delib.phase3_votes
        )
        conditions = [
            f"{r.persona_name}: {r.conditions}"
            for r in delib.phase3_votes
            if r.conditions
        ]
        conditions_text = (
            "\nConditions:\n" + "\n".join(conditions) if conditions else ""
        )

        synthesis_prompt = (
            f"MAGI SYSTEM - FINAL SYNTHESIS\n"
            f"==============================\n\n"
            f"Question: {delib.question}\n\n"
            f"Votes: {vote_summary}\n"
            f"Verdict: {delib.final_verdict}\n"
            f"{conditions_text}\n\n"
            f"Key positions:\n"
        )
        for r in delib.phase3_votes:
            synthesis_prompt += f"\n{r.persona_name}: {r.content}\n"

        synthesis_prompt += (
            f"\nAs the MAGI system synthesizer, produce a final consensus statement "
            f"that integrates the three perspectives. Be concise (3-5 sentences). "
            f"Honor the verdict while noting important dissents or conditions."
        )

        # Use MELCHIOR's persona for synthesis (as the logical aggregator)
        try:
            start = time.time()
            response = self.sync_client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a deliberation synthesizer. Your role is to produce "
                            "a final, unified consensus statement from three advisory perspectives. "
                            "Be concise, clear, and honor the democratic outcome."
                        ),
                    },
                    {"role": "user", "content": synthesis_prompt},
                ],
                max_completion_tokens=512,
            )
            duration_ms = (time.time() - start) * 1000

            usage = response.usage
            if usage:
                self.cost_tracker.record_call(
                    persona="MAGI_SYNTHESIS",
                    phase="synthesis",
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    duration_ms=duration_ms,
                )

            return response.choices[0].message.content or ""
        except Exception:
            # Fallback synthesis if API call fails
            vote_counts = {}
            for r in delib.phase3_votes:
                v = r.vote.value if r.vote else "UNKNOWN"
                vote_counts[v] = vote_counts.get(v, 0) + 1
            return (
                f"The MAGI system has reached a verdict of {delib.final_verdict}. "
                f"Vote breakdown: {', '.join(f'{r.persona_name}: {r.vote.value}' for r in delib.phase3_votes)}."
            )
