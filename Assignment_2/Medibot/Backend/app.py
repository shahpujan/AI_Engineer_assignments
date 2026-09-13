from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
)

from fastapi.middleware.cors import CORSMiddleware

from pydantic import (
    BaseModel,
    Field,
)

from typing import Literal

import secrets


# -------------------------------------------------------
# Import RAG functions
# -------------------------------------------------------

from .retreival_rerank import (
    hybrid_rag,
    contextualize_question,
)

from .sql_rag import sql_rag_chain


# =======================================================
# Step 1: Create FastAPI application
# =======================================================

app = FastAPI(
    title="MediBot API",
    description=(
        "Role-based Hybrid RAG and SQL RAG API "
        "for MediAssist Health Network"
    ),
    version="1.0.0",
)


# =======================================================
# Step 2: Configure CORS
# =======================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =======================================================
# Step 3: Security
# =======================================================

security = HTTPBearer()

# =======================================================
# Step 4: Demo Users
# =======================================================

USERS = {

    "dr.mehta": {
        "password": "doctor",
        "role": "doctor",
    },

    "nurse.priya": {
        "password": "nurse",
        "role": "nurse",
    },

    "billing.ravi": {
        "password": "billing",
        "role": "billing_executive",
    },

    "tech.anand": {
        "password": "technician",
        "role": "technician",
    },

    "admin.sys": {
        "password": "admin",
        "role": "admin",
    },
}

# =======================================================
# Step 5: Sessions
# =======================================================

SESSIONS = {}


# =======================================================
# Step 6: Collection Access Matrix
# =======================================================

COLLECTION_ACCESS = {

    "general": [
        "doctor",
        "nurse",
        "billing_executive",
        "technician",
        "admin",
    ],

    "clinical": [
        "doctor",
        "admin",
    ],

    "nursing": [
        "nurse",
        "doctor",
        "admin",
    ],

    "billing": [
        "billing_executive",
        "admin",
    ],

    "equipment": [
        "technician",
        "admin",
    ],
}


# =======================================================
# Step 7: SQL RAG Allowed Roles
# =======================================================

SQL_ALLOWED_ROLES = [
    "billing_executive",
    "admin",
]


# =======================================================
# Step 8: Request / Response Models
# =======================================================

class LoginRequest(BaseModel):
    username: str
    password: str


# -------------------------------------------------------
# NEW:
# Individual message coming from page.tsx
# -------------------------------------------------------

class HistoryMessage(BaseModel):

    role: Literal[
        "user",
        "assistant",
    ]

    content: str


# -------------------------------------------------------
# UPDATED:
# Chat request now accepts chat_history
# -------------------------------------------------------

class ChatRequest(BaseModel):
    question: str
    role: str
    chat_history: list[HistoryMessage] = Field(
        default_factory=list
    )
# =======================================================
# Step 9: Authenticate Session Token
# =======================================================

def get_session_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    token = credentials.credentials
    session = SESSIONS.get(token)
    if not session:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session token.",
        )

    return session

# =======================================================
# Step 10: Detect Requested Collection
# =======================================================

COLLECTION_KEYWORDS = {

    "billing": [
        "billing",
        "billing code",
        "billing codes",
        "insurance",
        "insurance code",
        "insurance codes",
        "diagnosis codes",
        "diagnosis code",
        "icd",
        "icd-10"
        "claim",
        "claims",
        "invoice",
        "invoices",
        "reimbursement",
        "payment",
        "payments",
        "pre-auth",
        "pre-atuhorisation"
    ],

    "clinical": [
        "clinical",        
        "treatment",
        "treatments",
        "clinical protocol",
        "clinical protocols",
        "patient treatment",
        "treatment guideline",
        "treatment guidelines"
    ],

    "nursing": [
        "nursing",
        "nurse procedure",
        "nurse procedures",
        "nursing procedure",
        "nursing procedures",
        "icu nursing",
        "nursing protocol",
        "nursing protocols",
        "bedside care",
        "iv cannula",
        "cannula",
    ],

    "equipment": [
        "equipment",
        "maintenance",
        "maintenance ticket",
        "maintenance tickets",
        "medical equipment",
        "medical device",
        "medical devices",
        "equipment repair",
        "machine repair",
        "device repair",
        "technician",
    ],
}


def detect_requested_collection(
    question: str,
):

    question_lower = question.lower()

    for collection, keywords in (
        COLLECTION_KEYWORDS.items()
    ):

        for keyword in keywords:

            if keyword in question_lower:

                return collection

    return None


# =======================================================
# Step 11: Detect Analytical Question
# =======================================================

def is_analytical_question(
    question: str,
) -> bool:

    analytical_keywords = [

        "how many",
        "count",
        "total",
        "average",
        "sum",
        "highest",
        "lowest",
        "most",
        "least",
        "number of",
        "percentage",
        "percent",

    ]

    question_lower = question.lower()

    return any(
        keyword in question_lower
        for keyword in analytical_keywords
    )


# =======================================================
# Step 12: Health Endpoint
# =======================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
        "service": "MediBot API",
    }


# =======================================================
# Step 13: Login Endpoint
# =======================================================

@app.post("/login")
def login(
    request: LoginRequest,
):

    username = request.username.strip()

    user = USERS.get(username)

    # ---------------------------------------------------
    # Validate credentials
    # ---------------------------------------------------

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )


    if request.password != user["password"]:

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
        )


    # ---------------------------------------------------
    # Create secure random session token
    # ---------------------------------------------------

    token = secrets.token_urlsafe(32)


    # ---------------------------------------------------
    # Store authentication information
    # ---------------------------------------------------

    SESSIONS[token] = {

        "username": username,
        "role": user["role"],
    }


    return {
        "token": token,
        "role": user["role"],
    }


# =======================================================
# Step 14: Accessible Collections Endpoint
# =======================================================

@app.get("/collections/{role}")
def get_collections(
    role: str,
    session=Depends(
        get_session_from_token
    ),
):

    authenticated_role = session["role"]
    requested_role = role.strip().lower()

    # ---------------------------------------------------
    # Prevent user from requesting another role
    # ---------------------------------------------------

    if requested_role != authenticated_role:

        raise HTTPException(
            status_code=403,
            detail=(
                "Access denied. "
                "You cannot view collections "
                "for another role."
            ),
        )


    # ---------------------------------------------------
    # Find collections accessible to role
    # ---------------------------------------------------

    collections = [
        collection
        for collection, roles
        in COLLECTION_ACCESS.items()
        if authenticated_role in roles
    ]

    return {
        "role": authenticated_role,
        "collections": collections,
    }


# =======================================================
# Step 15: Chat Endpoint
# =======================================================

@app.post("/chat")
def chat(
    request: ChatRequest,
    session=Depends(
        get_session_from_token
    ),
):

    # ---------------------------------------------------
    # 15.1 Get authenticated user role
    # ---------------------------------------------------

    authenticated_role = (
        session["role"]
    )
    requested_role = (
        request.role
        .strip()
        .lower()
    )


    # ---------------------------------------------------
    # 15.2 Prevent role spoofing
    #
    # Example:
    #
    # Nurse logs in but manually sends:
    #
    # role = "admin"
    #
    # This must be blocked.
    # ---------------------------------------------------

    if requested_role != authenticated_role:

        raise HTTPException(
            status_code=403,
            detail=(
                "Access denied. "
                "The requested role does not "
                "match your authenticated role."
            ),
        )

    # ---------------------------------------------------
    # 15.3 Validate question
    # ---------------------------------------------------

    question = request.question.strip()
    if not question:

        raise HTTPException(
            status_code=400,
            detail="Please enter a question.",
        )


    # ===================================================
    # 15.4 Convert Pydantic history into dictionaries
    # ===================================================

    chat_history = [

        {
            "role": message.role,
            "content": message.content,
        }

        for message
        in request.chat_history[-6:]

    ]

    # ---------------------------------------------------
    # Example:
    #
    # [
    #   {
    #      "role": "user",
    #      "content":
    #          "Tell me about IV cannula insertion"
    #   },
    #   {
    #      "role": "assistant",
    #      "content":
    #          "The recommended site selection..."
    #   }
    # ]
    # ---------------------------------------------------


    # ===================================================
    # 15.5 Contextualize Follow-up Question
    # ===================================================

    standalone_question = contextualize_question(
        question=question,
        chat_history=chat_history,
    )
    print("\n======================================")
    print("FASTAPI CHAT REQUEST")
    print("======================================")

    print(
        "Role:",
        authenticated_role,
    )

    print(
        "Original question:",
        question,
    )

    print(
        "Standalone question:",
        standalone_question,
    )

    print(
        "History messages:",
        len(chat_history),
    )

    print("======================================\n")


    # ===================================================
    # 15.6 Check Collection-Level RBAC
    #
    # IMPORTANT:
    #
    # We check the STANDALONE question rather than the
    # original follow-up.
    #
    # Example:
    #
    # Previous:
    # "Tell me about insurance claims"
    #
    # Current:
    # "How many are approved?"
    #
    # Standalone:
    # "How many insurance claims are approved?"
    #
    # Now FastAPI correctly detects "billing".
    # ===================================================

    requested_collection = (
        detect_requested_collection(
            standalone_question
        )
    )
    if requested_collection:
        allowed_roles = (
            COLLECTION_ACCESS.get(
                requested_collection,
                [],
            )
        )
        if (
            authenticated_role
            not in allowed_roles
        ):

            raise HTTPException(
                status_code=403,

                detail=(
                    f"Access denied. Your {authenticated_role} role does not have access to {requested_collection} information."
                ),
            )

    # ===================================================
    # 15.7 Decide SQL RAG vs Hybrid RAG
    #
    # Again use standalone_question.
    # ===================================================

    analytical_question = (
        is_analytical_question(
            standalone_question
        )
    )

    # ===================================================
    # 15.8 SQL RAG Route
    # ===================================================

    if analytical_question:


        # ------------------------------------------------
        # User is not allowed to access SQL-backed
        # analytical information.
        #
        # We deliberately do NOT mention "SQL analytics"
        # to the user.
        # ------------------------------------------------

        if (
            authenticated_role
            not in SQL_ALLOWED_ROLES
        ):

            raise HTTPException(
                status_code=403,

                detail=(
                    f"Access denied. Your "
                    f"{authenticated_role} role "
                    f"does not have permission "
                    f"to access this information."
                ),
            )


        # ------------------------------------------------
        # Run SQL RAG using standalone question.
        #
        # This also enables follow-up SQL questions.
        # ------------------------------------------------

        answer = sql_rag_chain(
            standalone_question
        )

        return {

            "answer": answer,
            "sources": [],
            "retrieval_type": "sql_rag",
            "role": authenticated_role,
        }

    # ===================================================
    # 15.9 Hybrid RAG Route
    # ===================================================

    # ---------------------------------------------------
    # IMPORTANT:
    # We already contextualized the question above.
    #
    # Therefore we send:
    #
    # chat_history=None
    #
    # Otherwise retreival_rerank.py would call the
    # contextualization LLM a SECOND time.
    # ---------------------------------------------------

    result = hybrid_rag(
        question=standalone_question,
        role=authenticated_role,
        chat_history=None,
    )

    # ===================================================
    # 15.10 Return Hybrid RAG Response
    # ===================================================

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "retrieval_type": "hybrid_rag",
        "role": authenticated_role,

    }