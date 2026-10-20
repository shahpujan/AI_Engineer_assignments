import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)

SAFE_REFUSAL = "Sorry, I cannot process this request."

# 1. Define the expected verdict structure
class GuardrailVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["ALLOW", "BLOCK"]
    reason: str
    layer: Literal["input", "output", "grounding"]
    safe_text: str | None = None

# 2. Validate and enforce the verdict
def enforce_guardrail(result: dict) -> bool:
    """
    True = continue processing
    False = block processing

    Missing, malformed or invalid verdicts
    are always blocked.
    """
    try:
        verdict = GuardrailVerdict.model_validate(result)

        if not verdict.reason.strip():
            logger.warning(
                "Guardrail blocked: missing reason"
            )
            return False

        if verdict.verdict == "ALLOW":
            if verdict.layer == "input" and (
                not verdict.safe_text
                or not verdict.safe_text.strip()
            ):
                logger.warning(
                    "Guardrail blocked: missing safe input"
                )
                return False

            return True

        logger.warning(
            "Guardrail blocked | layer=%s | reason=%s",
            verdict.layer,
            verdict.reason,
        )
        return False

    except (ValidationError, TypeError, ValueError):
        logger.warning(
            "Guardrail blocked: malformed or missing verdict"
        )
        return False
