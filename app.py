import streamlit as st
from langchain_community.utilities import SQLDatabase
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from urllib.parse import quote_plus
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
import os
import re
import time
import hashlib
import pandas as pd
import ast
from dotenv import load_dotenv
from difflib import SequenceMatcher
from decimal import Decimal
load_dotenv()

# Page Config
st.set_page_config(
    page_title="Text-to-SQL Chatbot",
    page_icon="database",
    layout="wide"
)

st.title("Text-to-SQL RAG Chatbot")
st.caption("Connect any MySQL database and ask questions in plain English.")
# Modern UI Styling
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0B1120 0%, #111827 55%, #172554 100%);
        color: #F1F5F9;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827, #1E293B);
        border-right: 1px solid #334155;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    h1 {
        color: #F8FAFC !important;
        font-weight: 800 !important;
        letter-spacing: -1px;
    }

    h2, h3 {
        color: #E2E8F0 !important;
    }

    div[data-testid="stMetric"] {
        background: linear-gradient(145deg, #1E293B, #172033);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
    }

    div[data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
    }

    div[data-testid="stMetricValue"] {
        color: #38BDF8 !important;
        font-weight: 750;
    }

    div[data-testid="stButton"] > button {
        border-radius: 10px;
        border: 1px solid #38BDF8;
        background: linear-gradient(90deg, #0284C7, #2563EB);
        color: white;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    div[data-testid="stButton"] > button:hover {
        border-color: #7DD3FC;
        box-shadow: 0 0 16px rgba(56, 189, 248, 0.25);
        color: white;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea {
        background-color: #111827;
        color: #F8FAFC;
        border: 1px solid #334155;
        border-radius: 10px;
    }

    div[data-testid="stChatInput"] {
        border: 1px solid #334155;
        border-radius: 14px;
    }

    div[data-testid="stDataFrame"],
    div[data-testid="stTable"] {
        border: 1px solid #334155;
        border-radius: 12px;
        overflow: hidden;
    }

    hr {
        border-color: #334155;
    }
</style>
""", unsafe_allow_html=True)
# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "semantic_cache" not in st.session_state:
    st.session_state.semantic_cache = {}
if "metrics" not in st.session_state:
    st.session_state.metrics = {
        "total_queries": 0,
        "successful_queries": 0,
        "failed_queries": 0,
        "cache_hits": 0,
        "self_healed": 0,
        "avg_response_time": 0.0,
        "response_times": []
    }


# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────

def clean_sql(sql: str) -> str:
    sql = re.sub(r"```sql|```", "", sql, flags=re.IGNORECASE)
    match = re.search(r"(SELECT|INSERT|UPDATE|DELETE|WITH)", sql, re.IGNORECASE)
    if match:
        sql = sql[match.start():]
    return sql.strip()


# --- SCHEMA RETRIEVAL (LIGHTWEIGHT RAG) ---

def retrieve_relevant_schema(db, question: str, top_k: int = 5) -> str:
    """Retrieve database tables relevant to the user's question."""

    tables = db.get_usable_table_names()

    if not tables:
        return ""

    question_words = set(
        re.findall(r"[a-zA-Z_]+", question.lower())
    )

    stop_words = {
        "show", "give", "find", "get", "list", "display",
        "the", "a", "an", "of", "for", "to", "in", "on",
        "by", "with", "and", "or", "from", "each", "all",
        "top", "total", "number", "me", "what", "which",
        "how", "many", "much", "their", "them"
    }

    question_words -= stop_words

    # Retrieve table schemas and rank them by relevance.
    ranked_tables = []

    for table in tables:
        try:
            table_schema = db.get_table_info(
                table_names=[table]
            )

            schema_words = set(
                re.findall(
                    r"[a-zA-Z_]+",
                    f"{table} {table_schema}".lower()
                )
            )

            score = len(question_words & schema_words)

            ranked_tables.append(
                (score, table, table_schema)
            )

        except Exception as e:
            print(f"Schema retrieval warning for {table}: {e}")

    ranked_tables.sort(
        key=lambda item: item[0],
        reverse=True
    )

    # Fall back to the full schema if nothing matches.
    relevant = [
        item for item in ranked_tables if item[0] > 0
    ][:top_k]

    if not relevant:
        return db.get_table_info()

    return "\n\n".join(
        schema for _, _, schema in relevant
    )


def retrieve_relevant_schema_faiss(db, question: str, top_k: int = 5) -> str:
    """Retrieve relevant database schemas using FAISS vector search."""

    try:
        tables = db.get_usable_table_names()

        if not tables:
            return ""

        documents = []

        for table in tables:
            try:
                schema = db.get_table_info(table_names=[table])

                documents.append(
                    Document(
                        page_content=f"Table: {table}\n{schema}",
                        metadata={"table_name": table}
                    )
                )
            except Exception as e:
                print(f"Schema retrieval warning for {table}: {e}")

        if not documents:
            return db.get_table_info()

        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        vector_store = FAISS.from_documents(
            documents,
            embeddings
        )

        results = vector_store.similarity_search(
            question,
            k=min(top_k, len(documents))
        )

        if not results:
            return db.get_table_info()

        return "\n\n".join(doc.page_content for doc in results)

    except Exception as e:
        print(f"FAISS schema retrieval failed: {e}")
        return db.get_table_info()

# ── INPUT VALIDATION ──────────────────────────────────────────────────────────

GREET_PATTERNS = re.compile(
    r"^\s*(hi|hello|hey|hiya|howdy|namaste|helo|helllo|sup|whatsup|what'?s up|good\s*(morning|evening|afternoon)|how are you|how r u)\s*[\?\!\.]*\s*$",
    re.IGNORECASE
)

GIBBERISH_PATTERN = re.compile(r"^[^a-zA-Z0-9\s]{3,}$")

def is_too_short(text: str) -> bool:
    return len(text.strip()) < 5

def is_greeting(text: str) -> bool:
    return bool(GREET_PATTERNS.match(text.strip()))

def is_gibberish(text: str) -> bool:
    words = text.strip().split()
    if len(words) == 1 and len(words[0]) < 3:
        return True
    if GIBBERISH_PATTERN.match(text.strip()):
        return True
    non_alpha = sum(1 for c in text if not c.isalnum() and c != ' ')
    if len(text) > 0 and (non_alpha / len(text)) > 0.6:
        return True
    return False

def is_off_topic(text: str) -> bool:
    off_topic_keywords = [
        "write a poem", "tell me a joke", "what is life", "weather",
        "news today", "stock price", "movie", "recipe", "translate",
        "capital of", "who is the president", "football", "cricket score",
        "what time is it", "calculate", "math problem"
    ]
    lower = text.lower()
    return any(kw in lower for kw in off_topic_keywords)

def validate_input(question: str) -> tuple[bool, str]:
    if is_too_short(question):
        return False, "Query is too short. Please be more specific, e.g: *'Show all customers'* or *'Total sales last month'*"

    if is_greeting(question):
        return False, "Hello! I am a SQL assistant. Ask something about your database, e.g:\n- *'Show top 10 customers'*\n- *'Total revenue this month'*\n- *'List all products with price > 500'*"

    if is_gibberish(question):
        return False, "Could not understand that. Please write your question clearly in English, e.g: *'How many orders were placed today?'*"


    db_keywords = [
        "show", "list", "find", "get", "how many", "count", "total",
        "average", "avg", "max", "min", "top", "all", "where", "which",
        "who", "what", "when", "select", "fetch", "display", "give me",
        "tell me", "records", "rows", "data", "table", "column", "from",
        "between", "latest", "recent", "last", "first", "most", "least",
        "product", "products", "revenue", "sales", "quantity",
        "price", "payment", "payments", "successful", "failed",
        "pending", "customer", "customers", "order", "orders",
        "profit", "amount", "sum", "highest", "lowest",
        "rank", "ranking", "group", "each", "per", "include",
        "excluding", "average", "monthly", "daily", "weekly",
        "schema", "columns", "tables", "database", "status"
    ]
    lower = question.lower()
    has_db_intent = any(kw in lower for kw in db_keywords)

    if not has_db_intent:
        return False, "This does not look like a database query. Try asking for specific data, e.g:\n- *'Show all orders from last week'*\n- *'Which product has the highest sales?'*"

    return True, ""


# ── SEMANTIC CACHE ────────────────────────────────────────────────────────────

def get_question_hash(question: str) -> str:
    return hashlib.md5(question.strip().lower().encode()).hexdigest()

def semantic_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def find_cache_hit(question: str, threshold: float = 0.85) -> dict | None:
    cache = st.session_state.semantic_cache

    exact_key = get_question_hash(question)
    if exact_key in cache:
        return cache[exact_key]

    for cached_q, cached_entry in cache.items():
        if "original_question" in cached_entry:
            sim = semantic_similarity(question, cached_entry["original_question"])
            if sim >= threshold:
                return cached_entry

    return None

def add_to_cache(question: str, sql: str, result_df, result_str: str):
    key = get_question_hash(question)
    st.session_state.semantic_cache[key] = {
        "original_question": question,
        "sql": sql,
        "result_df": result_df,
        "result_str": result_str
    }


def retrieve_relevant_schema(db, question: str, top_k: int = 5) -> str:
    """
    Retrieve database tables and columns relevant to the question.
    Uses lightweight keyword-based schema retrieval.
    """
    question_words = set(
        re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", question.lower())
    )

    stop_words = {
        "show", "list", "find", "give", "tell", "what", "which",
        "where", "when", "how", "many", "much", "the", "and",
        "for", "from", "with", "that", "are", "was", "were",
        "all", "top", "each", "per", "get", "display", "me",
        "please", "into", "including", "their", "total"
    }

    keywords = {
        word for word in question_words
        if len(word) > 2 and word not in stop_words
    }

    tables = sorted(db.get_usable_table_names())

    if not tables:
        return db.get_table_info()

    scored_tables = []

    for table in tables:
        try:
            table_schema = db.get_table_info(
                table_names=[table]
            )

            table_words = set(
                re.findall(
                    r"[a-zA-Z_][a-zA-Z0-9_]*",
                    table.lower()
                )
            )

            schema_words = set(
                re.findall(
                    r"[a-zA-Z_][a-zA-Z0-9_]*",
                    table_schema.lower()
                )
            )

            # Table-name matches receive extra weight.
            score = (
                3 * len(keywords & table_words)
                + len(keywords & schema_words)
            )

            if score > 0:
                scored_tables.append(
                    (score, table, table_schema)
                )

        except Exception as e:
            print(f"Schema retrieval warning for {table}: {e}")

    # Fall back to the full schema if no relevant table is found.
    if not scored_tables:
        return db.get_table_info()

    scored_tables.sort(
        key=lambda item: (-item[0], item[1])
    )

    selected = scored_tables[:top_k]

    return "\n\n".join(
        schema for _, _, schema in selected
    )


# ── SELF-HEALING SQL ──────────────────────────────────────────────────────────

def build_sql_chain(db, llm):
    template = """You are an expert MySQL data analyst.
Convert the question to a valid MySQL query.

=== DATABASE SCHEMA ===
{schema}

=== STRICT RULES ===
1. Return ONLY the raw SQL query — no explanation, no markdown
2. Single line only
3. Use backticks for column/table names with spaces or reserved words
4. Use LIMIT 100 unless user asks for all
5. Never use SELECT *
6. Only use tables and columns that exist in the schema above
7. Always qualify columns with table aliases when using JOIN.
8. Never use an unqualified column if multiple tables contain that column.
9. Use c.customer_id instead of customer_id when querying customers c.

Question: {question}
SQL Query:"""

    prompt = ChatPromptTemplate.from_template(template)

    def get_schema(inputs):
        question = inputs.get("question", "")
        return retrieve_relevant_schema(db, question)

    chain = (
        RunnablePassthrough.assign(schema=get_schema)
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain

def self_healing_execute(db, llm, question: str, max_retries: int = 2):
    chain = build_sql_chain(db, llm)
    raw_sql = chain.invoke({"question": question})
    cleaned_sql = clean_sql(raw_sql)

    last_error = None
    healed = False

    for attempt in range(max_retries + 1):
        try:
            
            result = db.run(cleaned_sql, include_columns=True)



            try:
                data = ast.literal_eval(result)
                df = pd.DataFrame(data)
                return cleaned_sql, df, None, healed, None
            except (ValueError, SyntaxError, TypeError):
                try:
                    import re
                    from datetime import date, datetime

                    safe_result = re.sub(
                        r"datetime\.date\((\d{4}),\s*(\d{1,2}),\s*(\d{1,2})\)",
                        r"date(\1, \2, \3)",
                        result
                    )
                    safe_result = re.sub(
                        r"Decimal\('([^']*)'\)",
                        r"\1",
                        safe_result
                    )
                    data = eval(
                        safe_result,
                        {"__builtins__": {}},
                        {"date": date, "datetime": datetime}
                    )
                    df = pd.DataFrame(data)
                    return cleaned_sql, df, None, healed, None

                except Exception:
                    return cleaned_sql, None, str(result), healed, None


        except Exception as e:
            last_error = str(e)
            print(f"SQL execution error: {last_error}")
            print(f"Failed SQL: {cleaned_sql}") 

            if attempt < max_retries:
                
                fix_template = """You are a MySQL expert. The following SQL query produced an error.
Fix the query and return ONLY the corrected SQL — no explanation, no markdown.

Original Question: {question}

Broken SQL:
{broken_sql}

Error:
{error}

Database Schema:
{schema}

Rules:
1. Use only tables and columns that exist in the database schema.
2. Always qualify columns with table aliases when multiple tables are joined.
   Example: c.customer_id instead of customer_id.
3. Use the correct table alias for every selected column.
4. Preserve the original question's intent.
5. Return only one valid MySQL query.
6. Do not include markdown code fences.




Corrected SQL:"""

                fix_prompt = ChatPromptTemplate.from_template(fix_template)
                fix_chain = fix_prompt | llm | StrOutputParser()

                fixed_raw = fix_chain.invoke({
                    "question": question,
                    "broken_sql": cleaned_sql,
                    "error": last_error,
                    "schema": db.get_table_info()
                })
                cleaned_sql = clean_sql(fixed_raw)
                healed = True

    return cleaned_sql, None, None, healed, last_error


# ── METRICS ──────────────────────────────────────────────────────────────────

def update_metrics(success: bool, response_time: float, cache_hit: bool = False, healed: bool = False):
    m = st.session_state.metrics
    m["total_queries"] += 1
    if success:
        m["successful_queries"] += 1
    else:
        m["failed_queries"] += 1
    if cache_hit:
        m["cache_hits"] += 1
    if healed:
        m["self_healed"] += 1
    m["response_times"].append(response_time)
    m["avg_response_time"] = sum(m["response_times"]) / len(m["response_times"])


# ── SIDEBAR ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Database Connection")

    host = st.text_input("Host", value="localhost")
    port = st.number_input("Port", value=3306)
    username = st.text_input("Username", value="root")
    password = st.text_input("Password", type="password")
    database = st.text_input("Database Name")
    groq_key = st.text_input("Groq API Key", type="password")

    connect_btn = st.button("Connect to Database", use_container_width=True)

    if connect_btn:
        if not all([host, username, password, database, groq_key]):
            st.error("Please fill all fields.")
        else:
            try:
                with st.spinner("Connecting..."):
                    encoded_password = quote_plus(password)
                    
                mysql_uri = f"mysql+pymysql://{username}:{encoded_password}@{host}:{int(port)}/{database}"

# Configure connection settings
                connect_args = {"connect_timeout": 10}

# Enable SSL for cloud MySQL connections (Aiven)
                if host.strip().lower() not in ("localhost", "127.0.0.1"):
                    from pathlib import Path

                    ca_path = Path(__file__).parent / "ca.pem"

                    if not ca_path.exists():
                        raise FileNotFoundError(
                            f"SSL certificate not found: {ca_path}"
                        )

                    connect_args["ssl"] = {"ca": str(ca_path)}

                db = SQLDatabase.from_uri(
                    mysql_uri,
                    sample_rows_in_table_info=2,
                    engine_args={
                        "pool_pre_ping": True,
                        "pool_recycle": 280,
                        "connect_args": connect_args
                    }
                )


                llm = ChatGroq(
                        model="openai/gpt-oss-20b",
                        api_key=groq_key,
                        temperature=0,
                        max_tokens=1024,
                    )

                st.session_state.db = db
                st.session_state.llm = llm
                st.session_state.connected = True
                st.session_state.tables = db.get_usable_table_names()

                st.success("Connected successfully.")
                st.info(f"Tables: {', '.join(st.session_state.tables)}")

            except Exception as e:
                st.error(f"Connection failed: {str(e)}")

    # Metrics Dashboard
    if "connected" in st.session_state:
        st.divider()
        st.header("📊 Analytics Dashboard")

        m = st.session_state.metrics
        total = m["total_queries"]
        success_rate = (m["successful_queries"] / total * 100) if total > 0 else 0

        st.caption("Monitor your chatbot performance in real time")

        row1 = st.columns(3)
        row2 = st.columns(3)

        with row1[0]:
            st.metric("📝 Total Queries", total)

        with row1[1]:
            st.metric("✅ Successful", m["successful_queries"])

        with row1[2]:
            st.metric("❌ Failed", m["failed_queries"])

        with row2[0]:
            st.metric("🎯 Success Rate", f"{success_rate:.1f}%")

        with row2[1]:
            st.metric("⚡ Cache Hits", m["cache_hits"])

        with row2[2]:
            st.metric("🛠️ Self-Healed", m["self_healed"])

        if total > 0:
            st.metric("⏱️ Avg Response Time", f"{m['avg_response_time']:.2f}s")
            
        if st.button("Clear Cache", use_container_width=True):
            st.session_state.semantic_cache = {}
            st.success("Cache cleared.")

        
        if st.button("Reset Metrics", use_container_width=True):
            st.session_state.metrics = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "cache_hits": 0,
            "self_healed": 0,
            "avg_response_time": 0.0,
            "response_times": []
        }
        st.success("Metrics reset.")
        



# ── MAIN CHAT AREA ────────────────────────────────────────────────────────────

if "connected" not in st.session_state:
    st.info("Please connect to a database using the sidebar.")
    st.stop()

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "sql" in msg:
            with st.expander("Generated SQL"):
                st.code(msg["sql"], language="sql")
        if "table" in msg and msg["table"] is not None:
            st.dataframe(msg["table"], use_container_width=True)
        if "badges" in msg:
            st.caption(msg["badges"])

# Chat input
question = st.chat_input("Ask anything about your data...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):

        # Step 1: Input Validation
        is_valid, validation_msg = validate_input(question)

        if not is_valid:
            st.warning(validation_msg)
            st.session_state.messages.append({
                "role": "assistant",
                "content": validation_msg
            })

        else:
            start_time = time.time()

            # Step 2: Semantic Cache Check
            cache_entry = find_cache_hit(question)

            if cache_entry:
                elapsed = time.time() - start_time
                update_metrics(success=True, response_time=elapsed, cache_hit=True)

                st.success("Served from cache.")
                if cache_entry["result_df"] is not None:
                    st.dataframe(cache_entry["result_df"], use_container_width=True)
                else:
                    st.write(cache_entry["result_str"])

                with st.expander("Generated SQL"):
                    st.code(cache_entry["sql"], language="sql")

                st.caption("From cache")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Served from cache.",
                    "sql": cache_entry["sql"],
                    "table": cache_entry["result_df"],
                    "badges": "From cache"
                })

            else:
                # Step 3: Self-Healing SQL Execution
                with st.spinner("Generating SQL..."):
                    try:
                        db = st.session_state.db
                        llm = st.session_state.llm

                        sql, result_df, result_str, healed, error = self_healing_execute(
                            db, llm, question, max_retries=2
                        )

                        elapsed = time.time() - start_time

                        if error:
                            update_metrics(success=False, response_time=elapsed)
                            st.error(f"Query failed after retries.\n\nError: `{error}`")
                            st.info("Try rephrasing your question or check if the table and column names are correct.")
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": f"Query failed: {error}"
                            })

                        else:
                            update_metrics(success=True, response_time=elapsed, healed=healed)
                            add_to_cache(question, sql, result_df, result_str)

                            badges_list = [f"Response time: {elapsed:.2f}s"]
                            if healed:
                                badges_list.append("Auto-fixed by self-healing")
                            badges = "  |  ".join(badges_list)

                            if result_df is not None:
                                st.success(f"{len(result_df)} row(s) returned.")
                                st.dataframe(result_df, use_container_width=True)
                            else:
                                st.success("Query executed successfully.")
                                st.write(result_str)

                            with st.expander("Generated SQL"):
                                st.code(sql, language="sql")
                                if healed:
                                    st.info("This SQL was auto-fixed after an initial error.")

                            st.caption(badges)

                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": f"Query executed. {len(result_df) if result_df is not None else ''} row(s) returned.",
                                "sql": sql,
                                "table": result_df,
                                "badges": badges
                            })

                    except Exception as e:
                        elapsed = time.time() - start_time
                        update_metrics(success=False, response_time=elapsed)
                        st.error(f"Unexpected error: {str(e)}")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"Error: {str(e)}"
                        })
        st.rerun()                         
