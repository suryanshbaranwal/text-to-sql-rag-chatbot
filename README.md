# 🤖 Text-to-SQL RAG Chatbot

**Ask questions in plain English. Get SQL queries and database results instantly.**

An AI-powered chatbot that converts natural-language questions into SQL queries, executes them against a MySQL database, and displays results in an interactive Streamlit interface.

<p align="center">
  <a href="https://text-to-sql-rag-chatbot-sb-as.streamlit.app/">
    <strong>🚀 Try the Live Demo</strong>
  </a>
  &nbsp; | &nbsp;
  <a href="https://github.com/suryanshbaranwal/text-to-sql-rag-chatbot">
    <strong>💻 View Source Code</strong>
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" alt="Python"/>
  <img src="https://img.shields.io/badge/Framework-Streamlit-FF4B4B?logo=streamlit" alt="Streamlit"/>
  <img src="https://img.shields.io/badge/LLM-Groq-orange" alt="Groq"/>
  <img src="https://img.shields.io/badge/Database-MySQL-4479A1?logo=mysql" alt="MySQL"/>
  <img src="https://img.shields.io/badge/RAG-FAISS-green" alt="FAISS"/>
</p>

## ✨ Features

- 💬 **Natural Language to SQL:** Ask questions about your database in plain English.
- 🧠 **RAG-Based Schema Retrieval:** Retrieve relevant database schema information to help generate context-aware SQL.
- ⚡ **LLM-Powered SQL Generation:** Generate SQL queries using the Groq API.
- 🗄️ **MySQL Integration:** Connect to local or cloud-hosted MySQL databases.
- 📊 **Interactive Results:** View query results in structured tables.
- 🔄 **Error Handling:** Retry or repair certain SQL errors.
- 📈 **Analytics Dashboard:** Track query counts, success rate, failures, and response time.
- ☁️ **Cloud Deployment:** Access the application through Streamlit Community Cloud.

## 🔗 Live Demo

**[Open Text-to-SQL RAG Chatbot](https://text-to-sql-rag-chatbot-sb-as.streamlit.app/)**

The application has been tested with a MySQL database containing these tables:

`customers` · `order_items` · `orders` · `payments` · `products`

To use the application, provide your own MySQL connection details and Groq API key in the sidebar.

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Web Interface | Streamlit |
| LLM Provider | Groq API |
| LLM Framework | LangChain |
| Database | MySQL |
| Database Connectivity | SQLAlchemy, PyMySQL |
| Embeddings | Hugging Face Sentence Transformers |
| Vector Search | FAISS |
| Data Processing | Pandas, NumPy |

## 🏗️ How It Works

```mermaid
flowchart TD
    A[User asks a question] --> B[Retrieve relevant database schema]
    B --> C[LLM generates SQL]
    C --> D[Execute query against MySQL]
    D --> E[Display results in Streamlit]
    E --> F[Update analytics metrics]
```

1. The user enters a question in natural language.
2. The application retrieves relevant database schema information.
3. The LLM generates an SQL query using the available context.
4. The application executes the query against the connected MySQL database.
5. Results are displayed in a table, and query metrics are updated.

## 💡 Example Questions

Try asking:

- `Show the top 10 products by total revenue.`
- `Which are the top 5 customers by total spending?`
- `Show monthly sales for the last 12 months.`
- `How many orders are there in the database?`

The actual results depend on the connected database and its data.

## 🚀 Run Locally

### Prerequisites

- Python 3.10+ (Python 3.12 has been tested)
- MySQL Server or access to a MySQL database
- A Groq API key

### 1. Clone the repository

```bash
git clone https://github.com/suryanshbaranwal/text-to-sql-rag-chatbot.git
cd text-to-sql-rag-chatbot
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Start the application

```bash
python -m streamlit run app.py
```

Open the local URL shown in the terminal, usually `http://localhost:8501`.

### 5. Connect your database

Enter your MySQL host, port, username, password, database name, and Groq API key in the application's sidebar.

For cloud MySQL connections, configure the required SSL certificate as documented in the project.

## 🔐 Security Notes

- Never commit database passwords, Groq API keys, or other secrets to GitHub.
- Use a database account with only the permissions the application needs.
- Use encrypted connections when connecting to a cloud database.
- Do not expose production database credentials in screenshots, logs, or public documentation.

## 🗺️ Future Improvements

- Stronger SQL validation and read-only query enforcement.
- Improved query accuracy and schema retrieval.
- Query history and downloadable results.
- More robust automated testing.
- Enhanced visualizations and analytics.

## 👥 Contributors

- Suryansh Baranwal
- Abhishek Singh


---

**Built with Python, Streamlit, LangChain, Groq, FAISS, and MySQL.**