import os
import re

from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_classic.chains import create_sql_query_chain
from langchain_core.prompts import ChatPromptTemplate


# -------------------------------------------------------
# Step 1: Configuration
# -------------------------------------------------------

DB_PATH = "mediassist_data/db/mediassist.db"

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL")


# -------------------------------------------------------
# Step 2: Configure Groq LLM
# -------------------------------------------------------

llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=0,
    max_retries=2,
)


# -------------------------------------------------------
# Step 3: Connect to SQLite using LangChain
# -------------------------------------------------------

db = SQLDatabase.from_uri(
    f"sqlite:///{DB_PATH}"
)

print("✅ Connected to MediAssist SQLite database")
print("Tables:", db.get_usable_table_names())


# -------------------------------------------------------
# Step 4: Clean Generated SQL
# -------------------------------------------------------

def clean_sql(raw_sql: str) -> str:

    sql = raw_sql.strip()

    # Remove markdown code blocks
    sql = re.sub(
        r"```sql|```",
        "",
        sql,
        flags=re.IGNORECASE
    )

    # Extract everything after SQLQuery:
    if "SQLQuery:" in sql:
        sql = sql.split(
            "SQLQuery:",
            1
        )[1]

    # Remove anything after SQLResult: or Answer:
    sql = re.split(
        r"\bSQLResult:|\bAnswer:",
        sql,
        flags=re.IGNORECASE
    )[0]

    return sql.strip()


# -------------------------------------------------------
# Step 5: Create Natural Language → SQL Chain
# -------------------------------------------------------

sql_query_chain = create_sql_query_chain(
    llm,
    db
)

print("✅ SQL query generation chain ready")


# -------------------------------------------------------
# Step 6: Validate SQL
# -------------------------------------------------------

def validate_sql(sql: str):

    # SQL RAG should only read data
    if not sql.lower().startswith("select"):

        raise ValueError(
            "Only SELECT queries are allowed."
        )

    forbidden_words = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "create ",
        "truncate ",
    ]

    sql_lower = sql.lower()

    for word in forbidden_words:

        if word in sql_lower:

            raise ValueError(
                f"Unsafe SQL detected: "
                f"{word.strip()}"
            )


# -------------------------------------------------------
# Step 7: Prompt for Natural Language Answer
# -------------------------------------------------------

SYSTEM_PROMPT = """
You are MediBot, an assistant for MediAssist Health Network.

Answer the user's question using ONLY the SQL query result
provided to you.

Do not invent values or information that are not present
in the SQL result.

Be specific with numbers and facts from the data.

Give a concise and clear answer.
"""


answer_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            SYSTEM_PROMPT
        ),
        (
            "human",
            """
Question:
{question}

SQL Result:
{result}

Answer:
"""
        ),
    ]
)


# Prompt → Groq
answer_chain = answer_prompt | llm


# -------------------------------------------------------
# Step 8: SQL RAG Chain
# -------------------------------------------------------

def sql_rag_chain(question: str) -> str:

    # ---------------------------------------------------
    # 8.1 Generate SQL
    # ---------------------------------------------------

    raw_sql = sql_query_chain.invoke(
        {
            "question": question
        }
    )

    print(
        f"\n[debug] Raw SQL → {raw_sql}"
    )


    # Guard against completely empty SQL output
    if not raw_sql or not raw_sql.strip():

        return (
            "I don't have structured database information "
            "available to answer that question."
        )


    # ---------------------------------------------------
    # 8.2 Clean Generated SQL
    # ---------------------------------------------------

    sql = clean_sql(
        raw_sql
    )

    print(
        f"[debug] Cleaned SQL → {sql}"
    )


    # ---------------------------------------------------
    # 8.3 Handle N/A or unsupported database question
    # ---------------------------------------------------

    invalid_sql_values = {
        "N/A",
        "NA",
        "NONE",
        "NOT APPLICABLE",
        "NOT AVAILABLE",
    }

    if (
        not sql
        or sql.upper() in invalid_sql_values
    ):

        print(
            "[debug] No valid SQL could be generated."
        )

        return (
            "I don't have structured database information "
            "available to answer that question."
        )


    # ---------------------------------------------------
    # 8.4 Validate SQL
    # ---------------------------------------------------

    try:

        validate_sql(
            sql
        )

    except ValueError as error:

        print(
            f"[debug] SQL validation failed → {error}"
        )

        return (
            "I couldn't generate a valid read-only SQL query "
            "for that question."
        )


    # ---------------------------------------------------
    # 8.5 Execute SQL against SQLite
    # ---------------------------------------------------

    try:

        result = db.run(
            sql
        )

    except Exception as error:

        print(
            f"[debug] SQL execution failed → {error}"
        )

        return (
            "I’m sorry, I couldn’t find information relevant "
            "to your question in the available MediAssist data."
        )


    print(
        f"[debug] SQL Result → {result}"
    )


    # ---------------------------------------------------
    # 8.6 SQL Result → Natural Language Answer
    # ---------------------------------------------------

    response = answer_chain.invoke(
        {
            "question": question,
            "result": result,
        }
    )

    return response.content


print("✅ sql_rag_chain function ready")


# -------------------------------------------------------
# Step 9: RBAC Configuration
# -------------------------------------------------------

SQL_ALLOWED_ROLES = [
    "billing_executive",
    "admin",
]


# -------------------------------------------------------
# Step 10: Manual Ask Function
# -------------------------------------------------------

def ask_sql(question: str):

    print(
        f"\nQuestion: {question}"
    )

    try:

        answer = sql_rag_chain(
            question
        )

        print(
            f"\nAnswer: {answer}"
        )

    except Exception as error:

        print(
            f"\n❌ SQL RAG Error: {error}"
        )

    print(
        "-" * 60
    )


# -------------------------------------------------------
# Step 11: Manual Testing
# -------------------------------------------------------

if __name__ == "__main__":

    # ---------------------------------------------------
    # Get Role
    # ---------------------------------------------------

    role = input(
        "\nEnter role "
        "(billing_executive/admin): "
    ).strip().lower()


    if role not in SQL_ALLOWED_ROLES:

        print(
            f"\n❌ Role '{role}' does not have "
            f"access to SQL RAG."
        )

        raise SystemExit


    print(
        f"✅ SQL RAG access granted for: {role}"
    )


    # ---------------------------------------------------
    # Question Loop
    # ---------------------------------------------------

    while True:

        question = input(
            "\nEnter your SQL question "
            "(or type 'exit' to quit): "
        ).strip()


        if question.lower() == "exit":

            print(
                "Exiting SQL RAG..."
            )

            break


        if not question:

            print(
                "Please enter a question."
            )

            continue


        ask_sql(
            question
        )