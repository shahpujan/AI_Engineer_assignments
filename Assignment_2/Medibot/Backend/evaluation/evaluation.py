
import os
import sys
import types
import json
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# =========================================================
# STEP 0: Load environment variables
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

# MediBot/.env
load_dotenv(BASE_DIR.parent.parent / ".env")

from evaluation.heuristic_evals import run_heuristic_evals


# =========================================================
# Temporary workaround for RAGAS / LangChain compatibility
# =========================================================

vertexai_stub = types.ModuleType(
    "langchain_community.chat_models.vertexai"
)


class ChatVertexAI:
    pass


vertexai_stub.ChatVertexAI = ChatVertexAI

sys.modules[
    "langchain_community.chat_models.vertexai"
] = vertexai_stub


from datasets import Dataset
from retreival_rerank import hybrid_rag

from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

from ragas.metrics import (
    ResponseRelevancy,
    faithfulness,
    context_precision,
    context_recall,
)

from ragas.run_config import RunConfig

from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings


answer_relevancy_single = ResponseRelevancy(strictness=1)


# =========================================================
# STEP 1: Load evaluation questions from JSON
# =========================================================

json_path = BASE_DIR / "medibot_ragas_test_cases.json"

with open(json_path, "r", encoding="utf-8") as f:
    test_cases = json.load(f)

evaluation_rows = []
heuristic_rows = []

print(f"Loaded {len(test_cases)} evaluation questions")


# =========================================================
# STEP 2: Run MediBot RAG and heuristic evaluations
# =========================================================

for test in test_cases:

    print(f"\n===== Evaluating: {test['id']} =====")
    print(f"Question: {test['question']}")
    print(f"Role: {test['role']}")

    # Measure the full hybrid RAG execution time
    start_time = time.perf_counter()

    result = hybrid_rag(
        question=test["question"],
        role=test["role"],
        chat_history=None,
    )

    latency_seconds = time.perf_counter() - start_time

    # Temporary diagnostic: inspect actual MediBot metadata
    if test["id"] == "MED-001":
        print("\n===== SOURCE METADATA SAMPLE =====")
        print("SOURCES SAMPLE:", repr(result.get("sources")))
        print("ANSWER SAMPLE:", repr(result.get("answer")))

    # -----------------------------------------------------
    # Component 5: Run deterministic heuristic checks
    # -----------------------------------------------------

    heuristic_result = {
        **result,
        "latency_seconds": latency_seconds,
    }

    checks = run_heuristic_evals(heuristic_result, test)

    for check in checks:

        heuristic_rows.append({
            "test_id": test["id"],
            "role": test["role"],
            **check,
        })

        print(
            f"HEURISTIC: {check['key']} "
            #f"=> {'PASS' if check['score'] == 1 else 'FAIL'} "
            f"=> {('N/A' if check['score'] is None else 'PASS' if check['score'] == 1 else 'FAIL')} "
            f"| {check['comment']}"
        )

    # -----------------------------------------------------
    # Prepare the same response for RAGAS
    # -----------------------------------------------------

    evaluation_row = {
        "question": test["question"],
        "contexts": result["contexts"],
        "answer": result["answer"],
        "ground_truth": test["ground_truth"],
    }

    evaluation_rows.append(evaluation_row)

    print("\nRetrieved Contexts:")

    for i, context in enumerate(
        evaluation_row["contexts"], start=1
    ):
        print(f"\n--- Context {i} ---")
        print(context)

    print("\nMediBot Answer:")
    print(evaluation_row["answer"])

    print("\nGround Truth:")
    print(evaluation_row["ground_truth"])

    print(f"\nResponse latency: {latency_seconds:.2f} seconds")


# =========================================================
# STEP 2B: Save heuristic evaluation results
# =========================================================

heuristic_df = pd.DataFrame(heuristic_rows)

heuristic_path = BASE_DIR / "heuristic_results.csv"

heuristic_df.to_csv(
    heuristic_path,
    index=False,
)

print("\n===== HEURISTIC EVALUATION SUMMARY =====")

# summary = heuristic_df.groupby("key")["score"].agg(
#     passed="sum",
#     total="count",
# )

# summary["failed"] = summary["total"] - summary["passed"]
summary = heuristic_df.groupby("key")["score"].agg(
    passed=lambda s: (s == 1).sum(),
    failed=lambda s: (s == 0).sum(),
    not_applicable=lambda s: s.isna().sum(),
    total="size",
)

print(summary)

print(f"\nHeuristic results saved to: {heuristic_path}")


# =========================================================
# STEP 3: Create RAGAS evaluation dataset
# =========================================================

dataset = Dataset.from_list(evaluation_rows)

print(f"\nTotal questions prepared for RAGAS: {len(dataset)}")


# =========================================================
# STEP 4: Configure RAGAS evaluator
# =========================================================

ragas_llm = LangchainLLMWrapper(
    ChatGroq(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        temperature=0,
        max_tokens=8192,
        reasoning_effort="low",
        api_key=os.getenv("GROQ_API_KEY"),
    )
)

ragas_embeddings = LangchainEmbeddingsWrapper(
    HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5"
    )
)


# =========================================================
# STEP 5: Run RAGAS evaluation
# =========================================================

run_config = RunConfig(
    timeout=180,
    max_retries=5,
    max_workers=1,
)

ragas_result = evaluate(
    dataset=dataset,
    metrics=[
        faithfulness,
        answer_relevancy_single,
        context_precision,
        context_recall,
    ],
    llm=ragas_llm,
    embeddings=ragas_embeddings,
    run_config=run_config,
    raise_exceptions=True,
)

print("\n===== RAGAS EVALUATION RESULTS =====")
print(ragas_result)


# =========================================================
# STEP 6: Save individual question scores to CSV
# =========================================================

scores_df = ragas_result.to_pandas()

scores_df.insert(
    0,
    "test_id",
    [test["id"] for test in test_cases],
)

output_path = BASE_DIR / "ragas_results.csv"

scores_df.to_csv(
    output_path,
    index=False,
)

metric_columns = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]

aggregate_scores = scores_df[metric_columns].mean()

print("\n===== AGGREGATE RAGAS SCORES =====")
print(aggregate_scores.round(4))

aggregate_scores.to_csv(
    BASE_DIR / "ragas_aggregate_scores.csv",
    header=["average_score"],
)

print(f"\nRAGAS results saved to: {output_path}")
print(f"Heuristic results saved to: {heuristic_path}")

print("\n===== EVALUATION PIPELINE COMPLETED =====")
