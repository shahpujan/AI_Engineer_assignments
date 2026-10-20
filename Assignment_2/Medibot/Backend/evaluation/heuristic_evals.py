
import re

LATENCY_THRESHOLD_SECONDS = 15.0

ROLE_COLLECTIONS = {
    "doctor": {"clinical", "general"},
    "nurse": {"nursing", "general"},
    "billing_executive": {"billing", "general"},
    "technician": {"equipment", "general"},
    "admin": {"clinical", "nursing", "billing", "equipment", "general"},
}

REFUSAL_PHRASES = [
    "i don't have enough information",
    "i do not have enough information",
    "i cannot provide",
    "i can't provide",
    "i cannot assist",
    "i can't assist",
]


def is_refusal(answer):
    """Recognise known MediBot refusal responses."""
    if not isinstance(answer, str):
        return False

    answer = answer.strip().lower()
    return any(phrase in answer for phrase in REFUSAL_PHRASES)


def answer_not_empty(result, test):
    """Check that MediBot returns a non-empty answer."""
    answer = result.get("answer")

    passed = isinstance(answer, str) and bool(answer.strip())

    return {
        "key": "answer_not_empty",
        "score": int(passed),
        "comment": "Answer present" if passed else "Empty or null answer",
    }


def citation_present(result, test):
    """Check that substantive answers include explicit citations."""
    answer = result.get("answer") or ""

    if is_refusal(answer):
        return {
            "key": "citation_present",
            "score": None,
            "comment": "N/A: refusal response does not require a citation",
        }

    found = bool(
        re.search(r"\[Source:\s*[^\]]+\]", answer, re.I)
    )

    return {
        "key": "citation_present",
        "score": int(found),
        "comment": (
            "Explicit citation found"
            if found
            else "Missing explicit [Source: ...] citation"
        ),
    }


def response_within_latency(result, test):
    """Check RAG response latency against the 15-second threshold."""
    latency = result.get("latency_seconds")

    passed = (
        isinstance(latency, (int, float))
        and not isinstance(latency, bool)
        and 0 <= latency <= LATENCY_THRESHOLD_SECONDS
    )

    return {
        "key": "response_within_latency",
        "score": int(passed),
        "comment": (
            f"Latency {latency:.2f}s; limit {LATENCY_THRESHOLD_SECONDS:.0f}s"
            if isinstance(latency, (int, float))
            else "Latency measurement missing"
        ),
    }


def restricted_role_access(result, test):
    """Check returned source collections against role permissions."""
    role = test.get("role", "")
    allowed = ROLE_COLLECTIONS.get(role)

    if allowed is None:
        return {
            "key": "restricted_role_access",
            "score": 0,
            "comment": f"Unknown role: {role}",
        }

    sources = result.get("sources") or []

    if not sources:
        return {
            "key": "restricted_role_access",
            "score": None,
            "comment": "N/A: no source metadata available to verify RBAC",
        }

    collections = []

    for source in sources:
        if not isinstance(source, dict):
            return {
                "key": "restricted_role_access",
                "score": None,
                "comment": "Cannot verify RBAC: invalid source metadata",
            }

        collection = source.get("collection")

        if not collection:
            return {
                "key": "restricted_role_access",
                "score": None,
                "comment": "Cannot verify RBAC: collection metadata missing",
            }

        collections.append(str(collection).lower())

    restricted = [
        collection
        for collection in collections
        if collection not in allowed
    ]

    return {
        "key": "restricted_role_access",
        "score": int(not restricted),
        "comment": (
            f"Unauthorized collections: {restricted}"
            if restricted
            else f"All source collections permitted for {role}"
        ),
    }


def run_heuristic_evals(result, test):
    """Run all four deterministic heuristic evaluators."""
    checks = [
        answer_not_empty,
        citation_present,
        response_within_latency,
        restricted_role_access,
    ]

    return [check(result, test) for check in checks]
