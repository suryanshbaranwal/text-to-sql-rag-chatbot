
# Text-to-SQL RAG Chatbot

An AI-powered chatbot that converts natural language questions into MySQL queries and displays database results through a Streamlit interface.

## Features

- Ask questions about your database in plain English.
- Generate SQL queries using an LLM.
- Connect to a MySQL database.
- Display query results in tables.
- Automatically retry and repair certain SQL errors.
- Retrieve relevant database schema information.
- Monitor query performance using analytics metrics.

## Tech Stack

- Python
- Streamlit
- MySQL
- SQLAlchemy
- LangChain
- Groq API
- Hugging Face Sentence Transformers
- FAISS

## Prerequisites

- Python 3.10 or a compatible version
- MySQL Server
- A Groq API key

## Setup Instructions

1. Clone or download this repository.
2. Open the project folder in your terminal.
3. Create and activate a virtual environment.
4. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Run the application:

   ```bash
   streamlit run app.py
   ```

6. Open the local URL displayed in your terminal.

## Configuration

Enter your MySQL connection details and Groq API key in the application's connection form.

Never commit API keys, passwords, or other secrets to GitHub.

## Project Status

This project is under development. Features and dependencies may change as testing continues.

## Future Improvements

- Improve SQL generation accuracy.
- Expand schema retrieval and RAG capabilities.
- Add more robust SQL validation and error handling.
- Deploy the application for public access.

## Contributors

- Suryansh Baranwal
- Abhishek Singh

