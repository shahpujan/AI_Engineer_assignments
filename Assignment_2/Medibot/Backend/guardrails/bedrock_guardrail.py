
import os
import logging
from pathlib import Path

import boto3
from dotenv import load_dotenv
from functools import lru_cache

import json
import time
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
# --------------------------------------------------
# Configuration
# --------------------------------------------------

logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("medibot.audit")

def log_guardrail_event(result: dict, latency_ms: float):
    run = get_current_run_tree()

    event = {
        "event": "guardrail_decision",
        "trace_id": str(run.trace_id) if run else None,
        "run_id": str(run.id) if run else None,
        "layer": result["layer"],
        "verdict": result["verdict"],
        "reason": result["reason"],
        "policy_reasons": result.get("policy_reasons", []),
        "latency_ms": round(latency_ms, 2),
    }

    audit_logger.info(json.dumps(event))

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = Path(__file__).resolve().parents[2]


LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False

if not audit_logger.handlers:
    handler = logging.FileHandler(
        LOG_DIR / "medibot_audit.jsonl",
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)

load_dotenv(PROJECT_DIR / ".env")

@lru_cache(maxsize=1)
def get_bedrock_client():
    session = boto3.Session(
        profile_name=os.getenv("AWS_PROFILE", "medibot"),
        region_name=os.getenv("AWS_REGION"),
    )
    return session.client("bedrock-runtime")


# --------------------------------------------------
# Guardrails extract reasons
# --------------------------------------------------

def extract_guardrail_reasons(response: dict) -> list[dict]:
    """
    Extract policy categories from Bedrock assessments.
    Do not log user text, detected PII values, or matched text.
    """
    reasons = []

    for assessment in response.get("assessments", []):
        for policy_key, category_key in [
            ("topicPolicy", "topics"),
            ("contentPolicy", "filters"),
            ("wordPolicy", "customWords"),
            ("wordPolicy", "managedWordLists"),
            ("sensitiveInformationPolicy", "piiEntities"),
            ("sensitiveInformationPolicy", "regexes"),
            ("contextualGroundingPolicy", "filters"),
        ]:
            for item in assessment.get(policy_key, {}).get(category_key, []):
                if item.get("action") not in ("BLOCKED", "ANONYMIZED"):
                    continue

                reason = {
                    "policy": policy_key,
                    "category": item.get("name") or item.get("type") or category_key,
                    "action": item.get("action"),
                }

                reasons.append(reason)

    return reasons

# --------------------------------------------------
# Shared AWS Bedrock Guardrail Call
# --------------------------------------------------

def apply_bedrock_guardrail(
    text: str,
    source: str,
) -> dict:
    """
    Apply AWS Bedrock Guardrails to input or output.

    Returns a structured verdict.
    Any API error or unexpected response is BLOCKED.
    """

    layer = source.lower()

    try:
        # session = boto3.Session(
        #     profile_name=os.getenv("AWS_PROFILE", "medibot"),
        #     region_name=os.getenv("AWS_REGION"),
        # )

        # client = session.client("bedrock-runtime")
        client = get_bedrock_client()


        response = client.apply_guardrail(
            guardrailIdentifier=os.environ[
                "BEDROCK_GUARDRAIL_ID"
            ],
            guardrailVersion=os.getenv(
                "BEDROCK_GUARDRAIL_VERSION",
                "DRAFT",
            ),
            source=source,
            content=[
                {
                    "text": {
                        "text": text
                    }
                }
            ],
        )

        action = response.get("action")

        if action == "NONE":
            return {
                "verdict": "ALLOW",
                "reason": "No guardrail intervention",
                "layer": layer,
                "safe_text": text,
            }

        if action == "GUARDRAIL_INTERVENED":
            policy_reasons = extract_guardrail_reasons(response)

            logger.warning(
                "%s guardrail intervened: %s",
                source,
                response.get(
                    "actionReason",
                    "Policy intervention",
                ),
            )

            # Block all interventions for now,
            # including PII masking.
            return {
                "verdict": "BLOCK",
                "reason": "Guardrail intervention",
                "policy_reasons": policy_reasons, 
                "layer": layer,
                "safe_text": None,
            }

        logger.error(
            "Unexpected %s guardrail action: %r",
            source,
            action,
        )

    except Exception:
        logger.exception(
            "%s guardrail evaluation failed",
            source,
        )

    # Fail closed
    return {
        "verdict": "BLOCK",
        "reason": "Guardrail unavailable or invalid response",
        "policy_reasons": policy_reasons,
        "layer": layer,
        "safe_text": None,
    }

#---------------------------------------------------
#Trace
#---------------------------------------------------
@traceable(
    name="AWS Bedrock Guardrail Check",
    run_type="chain",
    process_inputs=lambda inputs: {
        "source": inputs.get("source"),
        "text": "[redacted]",
    },
    process_outputs=lambda outputs: {
        "verdict": outputs.get("verdict"),
        "reason": outputs.get("reason"),
        "policy_reasons": outputs.get("policy_reasons", []),
        "layer": outputs.get("layer"),
        "safe_text": "[redacted]",
    } if isinstance(outputs, dict) else {"result": "[redacted]"},
)
def traced_bedrock_guardrail(text: str, source: str) -> dict:
    start = time.perf_counter()

    result = apply_bedrock_guardrail(text=text, source=source)

    latency_ms = (time.perf_counter() - start) * 1000
    log_guardrail_event(result, latency_ms)

    return result



# --------------------------------------------------
# Input Guardrail
# --------------------------------------------------

def check_input_guardrail(question: str) -> dict:
    """
    Check the user question before it reaches MediBot.
    """

    # return apply_bedrock_guardrail(
    #     text=question,
    #     source="INPUT",
    # )
    return traced_bedrock_guardrail(
        text=question,
        source="INPUT",
    )


# --------------------------------------------------
# Output Guardrail
# --------------------------------------------------

def check_output_guardrail(answer: str) -> dict:
    """
    Check the generated answer before returning it.
    """

    # return apply_bedrock_guardrail(
    #     text=answer,
    #     source="OUTPUT",
    # )
    return traced_bedrock_guardrail(
        text=answer,
        source="OUTPUT",
    )