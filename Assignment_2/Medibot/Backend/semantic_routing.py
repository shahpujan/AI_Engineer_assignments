from semantic_router import Route
from semantic_router.encoders import HuggingFaceEncoder
from semantic_router.routers import SemanticRouter


# ============================================================
# 1. DEFINE ROUTES + UTTERANCES
# ============================================================

sql_route = Route(
    name="sql_rag",
    utterances=[
        # Claims analytics
        "How many claims are there?",
        "How many claims are pending?",
        "How many claims are approved?",
        "How many claims are rejected?",
        "What is the total claim amount?",
        "What is the average claim amount?",
        "Show me the number of claims by status",
        "Which department has the highest number of claims?",
        "Show claim counts by department",
        "What is the total amount of approved claims?",

        # Maintenance analytics
        "How many maintenance tickets are there?",
        "How many maintenance tickets are open?",
        "How many maintenance tickets are pending?",
        "How many maintenance tickets are closed?",
        "Show maintenance ticket counts by status",
        "Which equipment category has the most maintenance tickets?",
        "What is the number of maintenance tickets by category?",
    ],
)


hybrid_route = Route(
    name="hybrid_rag",
    utterances=[
        # General / HR documents
        "What is the annual leave entitlement?",
        "What is the total annual leave entitlement?",
        "How many days of annual leave are employees entitled to?",
        "Explain the annual leave policy",
        "What is the leave policy?",

        # General policies
        "What is the gift policy?",
        "What is the maximum permitted gift value?",
        "Explain the code of conduct",

        # Billing documents
        "Explain the claim submission process",
        "What documents are required for claim pre-authorisation?",
        "What is the claim escalation procedure?",
        "How do I submit a cashless claim?",
        "What is the approval turnaround time for pre-authorisation?",
        "What is the package for Type 2 diabetes without complications?",
        "What is the package for ICD code E11.9?",

        # Clinical / nursing documents
        "What cannula size is recommended for a patient under 5 kg?",
        "What is the site selection order for IV cannulation?",
        "What should a nurse do after two failed cannula attempts?",
        "Explain the IV cannulation procedure",

        # Equipment documents
        "What is the maintenance procedure for medical equipment?",
        "Explain the equipment maintenance policy",
    ],
)


# ============================================================
# 2. CREATE EMBEDDING ENCODER
# ============================================================

encoder = HuggingFaceEncoder(
    name="sentence-transformers/all-MiniLM-L6-v2"
)


# ============================================================
# 3. CREATE SEMANTIC ROUTER
# ============================================================

router = SemanticRouter(
    encoder=encoder,
    routes=[
        sql_route,
        hybrid_route,
    ],
    auto_sync="local",
)


# ============================================================
# 4. ROUTING FUNCTION
# ============================================================

def route_question(question: str) -> str:
    """
    Route a MediBot question to SQL RAG or Hybrid RAG.

    Returns:
        "sql_rag"
        "hybrid_rag"
    """

    result = router(question)

    print("\n==============================")
    print("SEMANTIC ROUTER")
    print("==============================")
    print("Question:", question)
    print("Selected route:", result.name)
    print("==============================\n")

    # Safe fallback:
    # if Semantic Router is uncertain and returns no route,
    # use document RAG rather than SQL.
    if not result.name:
        return "hybrid_rag"

    return result.name
if __name__ == "__main__":

    test_questions = [
        "How many claims are pending?",
        "What is the average claim amount?",
        "What is the total annual leave entitlement?",
        "Explain the claim submission process.",
        "How many maintenance tickets are open?",
        "What is the maintenance procedure for medical equipment?",
    ]

    for question in test_questions:

        route = route_question(question)

        print(
            f"{question} --> {route}"
        )