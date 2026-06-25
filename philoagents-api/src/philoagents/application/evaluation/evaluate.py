import asyncio
import os

import opik
from loguru import logger
from opik.evaluation import evaluate
from opik.evaluation.metrics import (
    ContextPrecision,
    ContextRecall,
    Hallucination,
    Moderation,
    LLMEvaluator,
)

from philoagents.application.conversation_service.generate_response import get_response
from philoagents.config import settings
from philoagents.domain.philosopher_factory import PhilosopherFactory


async def evaluation_task(x: dict) -> dict:
    """Calls agentic app logic to evaluate philosopher responses.

    Args:
        x: Dictionary containing evaluation data with the following keys:
            messages: List of conversation messages where all but the last are inputs
                and the last is the expected output
            philosopher_id: ID of the philosopher to use

    Returns:
        dict: Dictionary with evaluation results containing:
            input: Original input messages
            context: Context used for generating the response
            output: Generated response from philosopher
            expected_output: Expected answer for comparison (as a plain string)
    """

    philosopher_factory = PhilosopherFactory()
    philosopher = philosopher_factory.get_philosopher(x["philosopher_id"])

    input_messages = x["messages"][:-1]
    expected_output_message = x["messages"][-1]

    # Extract plain string content from the expected output message dict
    if isinstance(expected_output_message, dict):
        expected_output_str = expected_output_message.get("content", str(expected_output_message))
    else:
        expected_output_str = str(expected_output_message)

    response, latest_state = await get_response(
        messages=input_messages,
        philosopher_id=philosopher.id,
        philosopher_name=philosopher.name,
        philosopher_perspective=philosopher.perspective,
        philosopher_style=philosopher.style,
        philosopher_era=philosopher.era,
        philosopher_context="",
        new_thread=True,
    )
    
    # Extract retrieved contexts from ToolMessages in the conversation state
    retrieved_contexts = []
    for msg in latest_state.get("messages", []):
        if getattr(msg, "type", None) == "tool" or msg.__class__.__name__ == "ToolMessage":
            retrieved_contexts.append(msg.content)

    return {
        "input": input_messages,
        "context": retrieved_contexts,
        "output": response,
        "expected_output": expected_output_str,
    }


def get_used_prompts() -> list:
    client = opik.Opik()

    prompts = [
        client.get_prompt(name="philosopher_character_card"),
        client.get_prompt(name="summary_prompt"),
        client.get_prompt(name="extend_summary_prompt"),
    ]
    prompts = [p for p in prompts if p is not None]

    return prompts


def evaluate_agent(
    dataset: opik.Dataset | None,
    workers: int = 2,
    nb_samples: int | None = None,
) -> None:
    """Evaluates an agent using specified metrics and dataset.

    Runs evaluation using Opik framework with Groq as the LLM judge (no OpenAI key needed).
    Metrics used: Hallucination, AnswerRelevance, Moderation, ContextRecall, ContextPrecision.

    Args:
        dataset: Dataset containing evaluation examples.
            Must contain messages and philosopher_id.
        workers: Number of parallel workers to use for evaluation.
            Defaults to 2.
        nb_samples: Optional number of samples to evaluate.
            If None, evaluates the entire dataset.

    Raises:
        ValueError: If dataset is None
        AssertionError: If COMET_API_KEY is not set

    Returns:
        None
    """

    assert settings.COMET_API_KEY, (
        "COMET_API_KEY is not set. We need it to track the experiment with Opik."
    )

    if not dataset:
        raise ValueError("Dataset is 'None'.")

    # Expose OPENAI_API_KEY and OPENAI_API_BASE so LiteLLM routes judge calls to OpenCode
    os.environ["OPENAI_API_KEY"] = settings.OPENCODE_API_KEY
    os.environ["OPENAI_API_BASE"] = settings.OPENCODE_BASE_URL

    logger.info("Starting evaluation...")

    experiment_config = {
        "model_id": settings.OPENCODE_LLM_MODEL,
        "judge_model_id": f"openai/{settings.OPENCODE_LLM_MODEL_JUDGE}",
        "dataset_name": dataset.name,
    }
    used_prompts = get_used_prompts()

    judge_model = f"openai/{settings.OPENCODE_LLM_MODEL_JUDGE}"
    
    # Custom Answer Relevance Metric based on Context and Input
    custom_answer_relevance_prompt = """YOU ARE AN EXPERT IN NLP EVALUATION METRICS, SPECIALLY TRAINED TO ASSESS ANSWER RELEVANCE IN RESPONSES PROVIDED BY LANGUAGE MODELS. YOUR TASK IS TO EVALUATE THE RELEVANCE OF A GIVEN ANSWER FROM ANOTHER LLM BASED ON THE USER'S INPUT AND CONTEXT PROVIDED.

### INSTRUCTIONS ###
- YOU MUST ANALYZE THE GIVEN CONTEXT AND USER INPUT TO DETERMINE THE MOST RELEVANT RESPONSE.
- EVALUATE THE ANSWER FROM THE OTHER LLM BASED ON ITS ALIGNMENT WITH THE USER'S QUERY AND THE CONTEXT.
- ASSIGN A RELEVANCE SCORE BETWEEN 0.0 (COMPLETELY IRRELEVANT) AND 1.0 (HIGHLY RELEVANT).
- RETURN THE RESULT AS A VALID JSON OBJECT, INCLUDING THE SCORE AND A BRIEF EXPLANATION OF THE RATING.

### CHAIN OF THOUGHTS ###
1. **Understanding the Context and Input:**
   1.1. READ AND COMPREHEND THE CONTEXT PROVIDED.
   1.2. IDENTIFY THE KEY POINTS OR QUESTIONS IN THE USER'S INPUT THAT THE ANSWER SHOULD ADDRESS.

2. **Evaluating the Answer:**
   2.1. COMPARE THE CONTENT OF THE ANSWER TO THE CONTEXT AND USER INPUT.
   2.2. DETERMINE WHETHER THE ANSWER DIRECTLY ADDRESSES THE USER'S QUERY OR PROVIDES RELEVANT INFORMATION.
   2.3. CONSIDER ANY EXTRANEOUS OR OFF-TOPIC INFORMATION THAT MAY DECREASE RELEVANCE.

3. **Assigning a Relevance Score:**
   3.1. ASSIGN A SCORE BASED ON HOW WELL THE ANSWER MATCHES THE USER'S NEEDS AND CONTEXT.
   3.2. JUSTIFY THE SCORE WITH A BRIEF EXPLANATION THAT HIGHLIGHTS THE STRENGTHS OR WEAKNESSES OF THE ANSWER.

### WHAT NOT TO DO ###
- DO NOT GIVE A SCORE WITHOUT FULLY ANALYZING BOTH THE CONTEXT AND THE USER INPUT.
- AVOID SCORES THAT DO NOT MATCH THE EXPLANATION PROVIDED.
- DO NOT INCLUDE ADDITIONAL FIELDS OR INFORMATION IN THE JSON OUTPUT BEYOND "score" AND "reason".
- NEVER ASSIGN A PERFECT SCORE UNLESS THE ANSWER IS FULLY RELEVANT AND FREE OF ANY IRRELEVANT INFORMATION.

### INPUTS ###
Input:
{input}

Output:
{output}

Context:
{context}
"""

    custom_answer_relevance = LLMEvaluator(
        name="CustomAnswerRelevance",
        prompt_template=custom_answer_relevance_prompt,
        model=judge_model,
    )

    scoring_metrics = [
        Hallucination(model=judge_model),
        custom_answer_relevance,
        Moderation(model=judge_model),
        ContextRecall(model=judge_model),
        ContextPrecision(model=judge_model),
    ]

    logger.info("Evaluation details:")
    logger.info(f"Dataset: {dataset.name}")
    logger.info(f"Judge model: {judge_model}")
    logger.info(f"Metrics: {[m.__class__.__name__ for m in scoring_metrics]}")

    evaluate(
        dataset=dataset,
        task=lambda x: asyncio.run(evaluation_task(x)),
        scoring_metrics=scoring_metrics,
        experiment_config=experiment_config,
        task_threads=workers,
        nb_samples=nb_samples,
        prompts=used_prompts,
    )
