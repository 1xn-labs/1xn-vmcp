"""
Advanced reasoning tools including chain-of-thought and DSPy-style operations.

Note: These tools provide DSPy-like functionality without requiring the DSPy package.
If you need full DSPy features (optimization, compilation), install dspy-ai separately.
"""

import json
from typing import Any, Optional

import litellm

from llm_mcp.config import get_settings, DEFAULT_MODELS
from llm_mcp.models import ChainOfThoughtInput
from llm_mcp.utils import handle_litellm_error, format_error_response


async def chain_of_thought(params: ChainOfThoughtInput) -> str:
    """
    Answer a question using step-by-step chain-of-thought reasoning.

    This tool prompts the LLM to think through the problem step by step
    before providing a final answer, improving accuracy on complex questions.

    Args:
        params: Input parameters including:
            - question: The question to answer
            - context: Optional context to inform the answer
            - model: Model to use

    Returns:
        The reasoning steps and final answer.
    """
    settings = get_settings()
    model = params.model or DEFAULT_MODELS.get("reasoning", settings.default_model)

    prompt = """You are a careful reasoning assistant. Answer the question by thinking through it step by step.

"""

    if params.context:
        prompt += f"""Context:
{params.context}

"""

    prompt += f"""Question: {params.question}

Think through this step by step:
1. First, identify what the question is asking
2. Consider what information or reasoning is needed
3. Work through the logic step by step
4. Arrive at your answer

Respond in JSON format:
{{
    "reasoning": "Your step-by-step reasoning here...",
    "answer": "Your final answer"
}}"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            result["model"] = response.model
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "reasoning": content,
                    "answer": "See reasoning above",
                    "model": response.model,
                },
                indent=2,
            )

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def multi_step_reasoning(
    question: str,
    steps: Optional[list[str]] = None,
    model: Optional[str] = None,
) -> str:
    """
    Solve a problem using a predefined multi-step reasoning process.

    This tool guides the LLM through specific reasoning steps to ensure
    thorough analysis of complex problems.

    Args:
        question: The question or problem to solve
        steps: Custom reasoning steps (optional)
        model: Model to use

    Returns:
        Results from each reasoning step and final answer.
    """
    settings = get_settings()
    model = model or DEFAULT_MODELS.get("reasoning", settings.default_model)

    default_steps = [
        "Understanding: What is the core question or problem?",
        "Breakdown: What are the key components or sub-questions?",
        "Analysis: What facts, data, or reasoning apply to each component?",
        "Synthesis: How do the pieces fit together?",
        "Conclusion: What is the final answer or recommendation?",
    ]

    reasoning_steps = steps or default_steps

    steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(reasoning_steps)])

    prompt = f"""Solve the following problem by working through these reasoning steps:

{steps_text}

Problem: {question}

Work through each step carefully, then provide your final answer.

Respond in JSON format:
{{
    "steps": {{
        "step_1": "your response to step 1",
        "step_2": "your response to step 2",
        ...
    }},
    "final_answer": "your final answer"
}}"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            result["model"] = response.model
            result["reasoning_framework"] = reasoning_steps
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "raw_response": content,
                    "model": response.model,
                },
                indent=2,
            )

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def decompose_and_solve(
    problem: str,
    max_subproblems: int = 5,
    model: Optional[str] = None,
) -> str:
    """
    Decompose a complex problem into sub-problems and solve each.

    This tool breaks down complex problems into smaller, more manageable
    parts, solves each part, then synthesizes a final answer.

    Args:
        problem: The complex problem to solve
        max_subproblems: Maximum number of sub-problems to create
        model: Model to use

    Returns:
        Sub-problems, their solutions, and the synthesized answer.
    """
    settings = get_settings()
    model = model or DEFAULT_MODELS.get("reasoning", settings.default_model)

    prompt = f"""You are an expert problem solver. Solve this complex problem by:
1. Breaking it down into {max_subproblems} or fewer sub-problems
2. Solving each sub-problem
3. Combining the solutions into a final answer

Problem: {problem}

Respond in JSON format:
{{
    "sub_problems": [
        {{"problem": "sub-problem 1", "solution": "solution 1"}},
        {{"problem": "sub-problem 2", "solution": "solution 2"}}
    ],
    "synthesis": "How the sub-solutions combine",
    "final_answer": "The complete answer"
}}"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            result["model"] = response.model
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            return json.dumps(
                {"raw_response": content, "model": response.model},
                indent=2,
            )

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def self_critique(
    question: str,
    initial_answer: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate an answer, critique it, and provide an improved response.

    This tool implements a self-critique pattern where the model evaluates
    its own answer and improves upon it.

    Args:
        question: The question to answer
        initial_answer: Optional initial answer to critique (generates one if not provided)
        model: Model to use

    Returns:
        Initial answer, critique, and improved answer.
    """
    settings = get_settings()
    model = model or DEFAULT_MODELS.get("reasoning", settings.default_model)

    if initial_answer:
        critique_prompt = f"""Question: {question}

Initial Answer: {initial_answer}

Now critique this answer:
1. What are the strengths of this answer?
2. What are the weaknesses or gaps?
3. What could be improved?

Then provide an improved answer based on your critique.

Respond in JSON format:
{{
    "critique": {{
        "strengths": ["strength 1", "strength 2"],
        "weaknesses": ["weakness 1", "weakness 2"],
        "suggestions": ["improvement 1", "improvement 2"]
    }},
    "improved_answer": "your improved answer"
}}"""
    else:
        critique_prompt = f"""Question: {question}

First, provide an initial answer to this question.
Then critique your own answer:
1. What are the strengths of your answer?
2. What are the weaknesses or gaps?
3. What could be improved?

Finally, provide an improved answer based on your critique.

Respond in JSON format:
{{
    "initial_answer": "your first answer",
    "critique": {{
        "strengths": ["strength 1", "strength 2"],
        "weaknesses": ["weakness 1", "weakness 2"],
        "suggestions": ["improvement 1", "improvement 2"]
    }},
    "improved_answer": "your improved answer"
}}"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": critique_prompt}],
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            if initial_answer:
                result["initial_answer"] = initial_answer
            result["model"] = response.model
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            return json.dumps(
                {"raw_response": content, "model": response.model},
                indent=2,
            )

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def debate_reasoning(
    question: str,
    perspectives: Optional[list[str]] = None,
    model: Optional[str] = None,
) -> str:
    """
    Explore a question from multiple perspectives before concluding.

    This tool simulates a debate between different viewpoints to arrive
    at a more balanced and well-considered answer.

    Args:
        question: The question to debate
        perspectives: List of perspectives to consider (optional)
        model: Model to use

    Returns:
        Arguments from each perspective and a balanced conclusion.
    """
    settings = get_settings()
    model = model or DEFAULT_MODELS.get("reasoning", settings.default_model)

    default_perspectives = ["Optimist", "Skeptic", "Pragmatist"]
    perspectives = perspectives or default_perspectives

    perspectives_str = ", ".join(perspectives)

    prompt = f"""Consider this question from multiple perspectives: {perspectives_str}

Question: {question}

For each perspective:
1. Present the strongest arguments from that viewpoint
2. Acknowledge potential weaknesses

Then synthesize a balanced conclusion.

Respond in JSON format:
{{
    "perspectives": {{
        "{perspectives[0]}": {{
            "arguments": ["arg1", "arg2"],
            "weaknesses": ["weakness1"]
        }},
        ...
    }},
    "synthesis": "how the perspectives relate",
    "conclusion": "your balanced final answer"
}}"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            result["model"] = response.model
            result["perspectives_used"] = perspectives
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            return json.dumps(
                {"raw_response": content, "model": response.model},
                indent=2,
            )

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)


async def verify_with_evidence(
    claim: str,
    context: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Verify a claim by identifying supporting and contradicting evidence.

    This tool analyzes a claim and explicitly identifies evidence for
    and against it.

    Args:
        claim: The claim to verify
        context: Optional context containing relevant information
        model: Model to use

    Returns:
        Supporting evidence, contradicting evidence, and verdict.
    """
    settings = get_settings()
    model = model or DEFAULT_MODELS.get("reasoning", settings.default_model)

    prompt = f"""Analyze this claim and evaluate its validity.

Claim: {claim}
"""

    if context:
        prompt += f"""
Context:
{context}
"""

    prompt += """
Provide:
1. Evidence or reasoning that supports the claim
2. Evidence or reasoning that contradicts the claim
3. Your verdict on the claim's validity

Respond in JSON format:
{
    "supporting_evidence": ["evidence 1", "evidence 2"],
    "contradicting_evidence": ["evidence 1", "evidence 2"],
    "verdict": "supported|contradicted|uncertain|partially_supported",
    "confidence": 0.0-1.0,
    "explanation": "brief explanation of your verdict"
}"""

    try:
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        try:
            result = json.loads(content)
            result["model"] = response.model
            result["claim"] = claim
            return json.dumps(result, indent=2)
        except json.JSONDecodeError:
            return json.dumps(
                {"raw_response": content, "model": response.model},
                indent=2,
            )

    except Exception as e:
        error = handle_litellm_error(e, model)
        return format_error_response(error)
