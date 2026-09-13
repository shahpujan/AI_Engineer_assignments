import os
from dotenv import load_dotenv

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import (
    QdrantVectorStore,
    RetrievalMode,
    FastEmbedSparse,
)

from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
)

from langchain_groq import ChatGroq

from langchain_classic.chains.retrieval import (
    create_retrieval_chain
)

from langchain_classic.chains.combine_documents import (
    create_stuff_documents_chain,
)

from langchain_core.prompts import ChatPromptTemplate

from langchain_classic.retrievers import (
    ContextualCompressionRetriever
)

from langchain_classic.retrievers.document_compressors import (
    CrossEncoderReranker
)

from langchain_community.cross_encoders import (
    HuggingFaceCrossEncoder
)


# -------------------------------------------------------
# Step 1: Configuration
# -------------------------------------------------------

QDRANT_PATH = "./qdrant_data_hybrid"

QDRANT_COLLECTION_NAME = "mediassist_docs"

EMBED_MODEL_ID = (
    "sentence-transformers/all-MiniLM-L6-v2"
)


VALID_ROLES = [
    "doctor",
    "nurse",
    "billing_executive",
    "technician",
    "admin",
]


# -------------------------------------------------------
# Step 2: Load embedding models
# -------------------------------------------------------

embedder = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL_ID
)


sparse_embedder = FastEmbedSparse(
    model_name="Qdrant/bm25"
)


# -------------------------------------------------------
# Step 3: Connect to existing Qdrant collection
# -------------------------------------------------------

vectorstore = (
    QdrantVectorStore.from_existing_collection(
        embedding=embedder,
        sparse_embedding=sparse_embedder,
        path=QDRANT_PATH,
        collection_name=QDRANT_COLLECTION_NAME,
        retrieval_mode=RetrievalMode.HYBRID,
    )
)


print("✅ Connected to existing Qdrant collection")


# -------------------------------------------------------
# Step 4: Configure Groq LLM
# -------------------------------------------------------

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL")


llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=0,
    max_retries=2,
)

# -------------------------------------------------------
# Step 5: Cross-Encoder Reranker
# -------------------------------------------------------

cross_encoder = HuggingFaceCrossEncoder(
    model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
)

reranker = CrossEncoderReranker(
    model=cross_encoder,
    top_n=3
)


print("✅ Cross-encoder reranker ready")


# -------------------------------------------------------
# Step 6: Build Answer Prompt
# -------------------------------------------------------

system_prompt = """
You are MediBot, an assistant for MediAssist Health Network.

Answer the user's question using ONLY the information
provided in the retrieved context.

If the answer is not available in the context, say:
"I don't have enough information in the available documents."

Do not invent information.

Context:
{context}
"""
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        ("human", "{input}"),
    ]
)


# -------------------------------------------------------
# Step 7: Create Question Answer Chain
# -------------------------------------------------------

question_answer_chain = (
    create_stuff_documents_chain(
        llm,
        prompt,
    )
)
# =======================================================
# Step 8: Follow-up Question Contextualisation
# =======================================================

contextualize_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are a query rewriting assistant for MediBot.

Your job is to rewrite the user's latest question into a
complete standalone question using the previous conversation
history when necessary.

Rules:

1. Do NOT answer the question.
2. Only rewrite the question.
3. Use conversation history only when necessary.
4. Preserve the user's original meaning.
5. Do not invent information.
6. Resolve references such as:
   - it
   - this
   - that
   - they
   - those
   - what about...
   - what size...
   - what happens after...
   - how often...
7. If the current question is already a complete standalone
   question, return it unchanged.
8. Return ONLY the rewritten standalone question.
9. Do not include explanations, labels or quotation marks.

Example:

Conversation history:

user:
What is the site selection order for IV cannula insertion?

assistant:
The recommended order is forearm, antecubital fossa,
then dorsum of hand.

Current question:
What about children under 5 kg?

Standalone question:
What IV cannula size is recommended for a paediatric
patient under 5 kg?
""",
        ),
        (
            "human",
            """
Conversation history:
{chat_history}

Current question:
{question}
""",
        ),
    ]
)


contextualize_chain = contextualize_prompt | llm


# -------------------------------------------------------
# Step 8.1: Contextualize Question Function
# -------------------------------------------------------

def contextualize_question(
    question: str,
    chat_history: list | None = None,
) -> str:

    # ---------------------------------------------------
    # If this is the first question, there is no history.
    # Therefore there is nothing to contextualize.
    # ---------------------------------------------------

    if not chat_history:
        return question


    # ---------------------------------------------------
    # Keep only the most recent 6 messages.
    #
    # Example:
    #
    # user: Tell me about IV cannula insertion
    # assistant: ...
    # user: What about under 5 kg?
    #
    # ---------------------------------------------------

    recent_history = chat_history[-6:]


    # ---------------------------------------------------
    # Convert Python list of dictionaries into plain text
    # that the LLM can understand.
    # ---------------------------------------------------

    history_text = "\n".join(
        [
            (
                f"{message['role']}: "
                f"{message['content']}"
            )
            for message in recent_history
        ]
    )


    # ---------------------------------------------------
    # Ask Groq to turn the follow-up into a standalone
    # question.
    # ---------------------------------------------------

    response = contextualize_chain.invoke(
        {
            "chat_history": history_text,
            "question": question,
        }
    )


    standalone_question = (
        response.content.strip()
    )


    # ---------------------------------------------------
    # DEBUG
    #
    # Very useful while developing.
    # You can see exactly what MediBot changed.
    # ---------------------------------------------------

    print("\n======================================")
    print("CONVERSATION CONTEXTUALISATION")
    print("======================================")

    print("\nOriginal question:")
    print(question)

    print("\nStandalone question:")
    print(standalone_question)

    print("\n======================================\n")


    return standalone_question


# =======================================================
# Step 9: Hybrid RAG Function
# =======================================================

def hybrid_rag(
    question: str,
    role: str,
    chat_history: list | None = None,
):

    role = role.strip().lower()


    # ---------------------------------------------------
    # 9.1 Validate Role
    # ---------------------------------------------------

    if role not in VALID_ROLES:

        raise ValueError(
            f"Invalid role: {role}"
        )


    # ---------------------------------------------------
    # 9.2 Contextualize Current Question
    # ---------------------------------------------------

    standalone_question = contextualize_question(
        question=question,
        chat_history=chat_history,
    )


    # ---------------------------------------------------
    # Example:
    #
    # Original:
    # "What about children under 5 kg?"
    #
    # Standalone:
    # "What IV cannula size is recommended for a
    # paediatric patient under 5 kg?"
    #
    # From here onward, Qdrant uses the standalone
    # question.
    # ---------------------------------------------------


    # ---------------------------------------------------
    # 9.3 Create RBAC Filter
    # ---------------------------------------------------

    role_filter = Filter(
        must=[
            FieldCondition(
                key="metadata.access_roles",
                match=MatchValue(
                    value=role
                ),
            )
        ]
    )


    # ---------------------------------------------------
    # 9.4 Hybrid Retrieval - Top 10
    # ---------------------------------------------------

    hybrid_retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 10,
            "filter": role_filter,
        }
    )


    # ---------------------------------------------------
    # IMPORTANT CHANGE
    #
    # Search Qdrant with standalone_question,
    # NOT the ambiguous original follow-up.
    # ---------------------------------------------------

    debug_top10 = hybrid_retriever.invoke(
        standalone_question
    )


    print("\n======================================")
    print("HYBRID TOP 10 - BEFORE RERANKING")

    print(
        "Original Question:",
        question,
    )

    print(
        "Retrieval Question:",
        standalone_question,
    )

    print(
        "Role:",
        role,
    )

    print("======================================")


    for i, doc in enumerate(
        debug_top10,
        1,
    ):

        print(
            f"\n----- RESULT {i} -----"
        )

        print(
            "Source:",
            doc.metadata.get(
                "source_document"
            ),
        )

        print(
            "Section:",
            doc.metadata.get(
                "section_title"
            ),
        )

        print(
            "Collection:",
            doc.metadata.get(
                "collection"
            ),
        )

        print("\nCONTENT:")

        print(
            doc.page_content[:500]
        )


    print("\n======================================")


    # ---------------------------------------------------
    # 9.5 Cross-Encoder Reranking - Top 3
    # ---------------------------------------------------

    compression_retriever = (
        ContextualCompressionRetriever(
            base_retriever=hybrid_retriever,
            base_compressor=reranker,
        )
    )


    # ---------------------------------------------------
    # Cross encoder also receives standalone_question.
    # ---------------------------------------------------

    debug_docs = compression_retriever.invoke(
        standalone_question
    )


    print("\n======================================")
    print("RERANKED TOP 3 DOCUMENTS")

    print(
        "Original Question:",
        question,
    )

    print(
        "Retrieval Question:",
        standalone_question,
    )

    print(
        "Role:",
        role,
    )

    print("======================================")


    for i, doc in enumerate(
        debug_docs,
        1,
    ):

        print(
            f"\n----- CHUNK {i} -----"
        )

        print(
            "Source:",
            doc.metadata.get(
                "source_document"
            ),
        )

        print(
            "Section:",
            doc.metadata.get(
                "section_title"
            ),
        )

        print(
            "Collection:",
            doc.metadata.get(
                "collection"
            ),
        )

        print(
            "Roles:",
            doc.metadata.get(
                "access_roles"
            ),
        )

        print("\nCONTENT:")

        print(
            doc.page_content
        )

        print(
            "\n======================================"
        )


    # ---------------------------------------------------
    # 9.6 Create Hybrid RAG Chain
    # ---------------------------------------------------

    hybrid_rag_chain = (
        create_retrieval_chain(
            compression_retriever,
            question_answer_chain,
        )
    )


    # ---------------------------------------------------
    # 9.7 Run Question
    # ---------------------------------------------------
    # ---------------------------------------------------

    result = hybrid_rag_chain.invoke(
        {
            "input": standalone_question
        }
    )
    print("\n==============================")
    print("QUESTION:")
    print(standalone_question)

    print("\nRETRIEVED CONTEXT:")
    print("==============================")

    for i, doc in enumerate(result["context"], start=1):
        print(f"\n--- CHUNK {i} ---")
        print("Source:", doc.metadata.get("source_document"))
        print("Section:", doc.metadata.get("section_title"))
        print("Collection:", doc.metadata.get("collection"))
        print("Chunk type:", doc.metadata.get("chunk_type"))
        print("\nContent:")
        print(doc.page_content[:1500])



    # ---------------------------------------------------
    # 9.8 Prepare Sources
    # ---------------------------------------------------
    answer = result["answer"].strip()

    insufficient_phrases = [
        "i don't have enough information",
        "i do not have enough information",
        "i couldn't find enough information",
        "i could not find enough information",
        "i couldn't find relevant information",
        "i could not find relevant information",
        "not enough information",
        "insufficient information",
    ]

    answer_lower = answer.lower()

    has_insufficient_information = any(
        phrase in answer_lower
        for phrase in insufficient_phrases
    )

    sources = []
    if not has_insufficient_information:
        for doc in result["context"]:
            sources.append( {
                "source_document":
                    doc.metadata.get(
                        "source_document",
                        "unknown",
                    ),

                "section_title":
                    doc.metadata.get(
                        "section_title",
                        "unknown",
                    ),

                "collection":
                    doc.metadata.get(
                        "collection",
                        "unknown",
                    ),
            }
        )


    # ---------------------------------------------------
    # 9.9 Return Answer + Sources
    # ---------------------------------------------------

    return {
        "answer": result["answer"],
        "sources": sources,
    }


print("✅ Hybrid RAG function ready")


# =======================================================
# Step 10: Manual Testing with Conversation History
# =======================================================

if __name__ == "__main__":


    # ---------------------------------------------------
    # 10.1 Login / Choose Role
    # ---------------------------------------------------

    while True:

        role = input(
            "\nEnter role "
            "(doctor/nurse/billing_executive/"
            "technician/admin): "
        ).strip().lower()


        if role in VALID_ROLES:

            print(
                f"✅ Logged in as role: {role}"
            )

            break


        print(
            "❌ Invalid role. Please try again."
        )


    # ---------------------------------------------------
    # 10.2 Create Conversation History
    # ---------------------------------------------------
    #
    # This acts like temporary session memory while
    # testing from the terminal.
    #
    # Later FastAPI / frontend will provide this history.
    # ---------------------------------------------------

    chat_history = []


    # ---------------------------------------------------
    # 10.3 Conversation Loop
    # ---------------------------------------------------

    while True:

        question = input(
            "\nEnter your question "
            "(or type 'exit' to quit): "
        ).strip()


        if question.lower() == "exit":

            print(
                "Exiting MediBot..."
            )

            break


        if not question:

            print(
                "Please enter a question."
            )

            continue


        try:

            # ------------------------------------------------
            # Pass conversation history into Hybrid RAG
            # ------------------------------------------------

            result = hybrid_rag(
                question=question,
                role=role,
                chat_history=chat_history,
            )


            print(
                f"\nQuestion: {question}"
            )


            print(
                f"\nAnswer: "
                f"{result['answer']}"
            )


            print(
                "\nSources retrieved:"
            )


            for i, source in enumerate(
                result["sources"],
                start=1,
            ):

                print(
                    f"\n[{i}]"
                )

                print(
                    f"Source     : "
                    f"{source['source_document']}"
                )

                print(
                    f"Collection : "
                    f"{source['collection']}"
                )

                print(
                    f"Section    : "
                    f"{source['section_title']}"
                )


            print(
                "-" * 60
            )


            # ------------------------------------------------
            # Save successful User → Assistant turn
            # ------------------------------------------------

            chat_history.append(
                {
                    "role": "user",
                    "content": question,
                }
            )


            chat_history.append(
                {
                    "role": "assistant",
                    "content": result["answer"],
                }
            )


            # ------------------------------------------------
            # Keep only latest 6 messages.
            #
            # Prevents unlimited growth of conversation.
            # ------------------------------------------------

            chat_history = chat_history[-6:]


        except Exception as error:

            print(
                f"\n❌ Hybrid RAG Error: "
                f"{error}"
            )


    # ---------------------------------------------------
    # Step 11: Close Qdrant
    # ---------------------------------------------------

    vectorstore.client.close()