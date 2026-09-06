# BankScope Deployment & Configuration Guide

BankScope is engineered to run seamlessly across two primary execution targets:
1. **Local Development**: Configured via `.env` file connecting to local PostgreSQL or remote PostgreSQL.
2. **Streamlit Community Cloud**: Configured via Streamlit Cloud Secrets (`st.secrets`) connecting to managed cloud PostgreSQL (e.g., Neon, AWS RDS, Supabase).

---

## 1. Local Development Setup

### Prerequisites
- Python 3.10+ (tested and verified on Python 3.12 and 3.13)
- PostgreSQL 14+ (tested on PostgreSQL 18.0 and Neon Serverless Postgres)
- Canonical SQLite dataset (`data/raw/banking_dataset_kaggle/data/database/bank_sqlite.db`)

### Step-by-Step Instructions
1. **Clone the repository**:
   ```bash
   git clone https://github.com/Kurra-Srinivas/Banking-Data-Analytics.git
   cd "Banking Data Analytics"
   ```

2. **Set up Virtual Environment**:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables (`.env`)**:
   Create a `.env` file in the project root:
   ```env
   # PostgreSQL Connection (Local or Cloud)
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=bankscope_db
   DB_USER=postgres
   DB_PASSWORD=your_local_password
   DB_SSLMODE=prefer

   # Optional LLM Configuration (If omitted, Offline Demo Engine activates automatically)
   GEMINI_API_KEY=
   OPENAI_API_KEY=
   LLM_PROVIDER=
   ```

4. **Verify Database & Launch Dashboard**:
   ```bash
   python scripts/validate_postgres.py
   streamlit run dashboard/app.py
   ```

---

## 2. Streamlit Community Cloud Deployment

### Deployment Steps
1. **Verify Local Readiness**:
   Ensure all automated validation and regression tests pass locally:
   ```bash
   python scripts/validate_postgres.py
   python scratch/test_dashboard_e2e.py
   python scratch/test_nl_sql_engine.py
   python scratch/test_nl_sql_execution.py
   python scratch/test_sections_6_and_7.py
   ```

2. **Push to GitHub**:
   Ensure all runtime code and configuration files are pushed to your GitHub repository (`main` branch).
   > **Note**: Verify that `.env`, `.venv/`, `scratch/`, and `secrets.toml` are excluded via `.gitignore`.

3. **Log in to Streamlit Community Cloud**:
   Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with your GitHub account.

4. **Create New Application**:
   - Click **"Create app"** (or **"New app"**).
   - Select **"I already have an app"**.
   - Fill in repository details:
     - **Repository**: `Kurra-Srinivas/Banking-Data-Analytics`
     - **Branch**: `main`
     - **Main file path**: `dashboard/app.py`
     - **App URL**: `bankscope-analytics.streamlit.app` (or custom name of choice)

5. **Configure Advanced Settings**:
   - Click **"Advanced settings..."** before deploying.
   - **Python Version**: Select **3.12** (recommended and verified).
   - Navigate to the **Secrets** text box.

6. **Add Secrets Configuration**:
   Paste your Neon PostgreSQL credentials and optional LLM keys into the Secrets editor (see format below).

7. **Deploy**:
   - Click **"Deploy!"**.
   - Streamlit Cloud will automatically install dependencies from `requirements.txt`, load `.streamlit/config.toml` dark theme, inject credentials from `st.secrets`, and launch BankScope.

---

## 3. Streamlit Cloud Secrets Format

BankScope's configuration loader dynamically supports both standard flat keys and sectioned TOML tables.

### Option A: Flat Keys (Recommended)
Paste the following into your Streamlit Cloud **Secrets** editor:

```toml
# Cloud PostgreSQL Credentials (Neon / Managed Postgres)
DB_HOST = "ep-your-subdomain.region.aws.neon.tech"
DB_PORT = "5432"
DB_NAME = "bankscope"
DB_USER = "your_neon_username"
DB_PASSWORD = "your_neon_password"
DB_SSLMODE = "require"

# Optional LLM API Settings (Live Natural Language SQL Generation)
# If neither key is provided, BankScope runs in Offline Demo Synthesis Mode
GEMINI_API_KEY = "AIzaSy..."
OPENAI_API_KEY = "sk-..."
LLM_PROVIDER = "gemini" # Options: 'gemini', 'openai', or 'offline'
```

### Option B: Sectioned TOML Table
BankScope also recognizes standard `[postgres]` and `[connections.postgresql]` sections:

```toml
[postgres]
host = "ep-your-subdomain.region.aws.neon.tech"
port = "5432"
dbname = "bankscope"
user = "your_neon_username"
password = "your_neon_password"
sslmode = "require"

[llm]
gemini_api_key = "AIzaSy..."
openai_api_key = "sk-..."
provider = "gemini"
```

---

## 4. Required Configuration Reference

| Parameter | Type | Required | Description | Default |
| :--- | :---: | :---: | :--- | :--- |
| `DB_HOST` | string | **Yes** | PostgreSQL server hostname or IP address | `localhost` |
| `DB_PORT` | integer | **Yes** | PostgreSQL server port | `5432` |
| `DB_NAME` | string | **Yes** | Target PostgreSQL database name | `bankscope_db` |
| `DB_USER` | string | **Yes** | Database username | `postgres` |
| `DB_PASSWORD` | string | **Yes** | Database user password (URL-encoded automatically) | `""` |
| `DB_SSLMODE` | string | **Yes (Cloud)** | SSL verification mode (`require` for Neon, `prefer`, `disable`) | `None` (Local) / `require` (Cloud) |
| `GEMINI_API_KEY` | string | Optional | Google Gemini API key for live NL-SQL generation | `None` |
| `OPENAI_API_KEY` | string | Optional | OpenAI API key for live NL-SQL generation | `None` |
| `LLM_PROVIDER` | string | Optional | Override active LLM engine (`gemini`, `openai`, `offline`) | Auto-detect |

---

## 5. Cloud Database Requirements

For BankScope to operate on Neon or another cloud PostgreSQL instance:

1. **PostgreSQL Version**: PostgreSQL 14 or higher (Neon runs PostgreSQL 16/17).
2. **SSL Requirement**: Cloud PostgreSQL instances (like Neon) require TLS encryption (`DB_SSLMODE=require`).
3. **Schema Architecture**:
   - `public` schema containing the 7 canonical warehouse tables:
     - `customers` (50,000 rows)
     - `accounts` (75,000 rows)
     - `cards` (100,000 rows)
     - `loans` (30,000 rows)
     - `merchants` (5,000 rows)
     - `branches` (500 rows)
     - `transactions` (1,000,000 rows)
   - `uploads` schema:
     - Created automatically on first CSV upload via `CREATE SCHEMA IF NOT EXISTS uploads;`
     - Stores user-ingested tables (`uploads.upload_*`) and metadata (`uploads._upload_metadata`).
4. **Database Privileges**:
   - Read access (`SELECT`) on `public.*`.
   - Write access (`CREATE TABLE`, `INSERT`) on `uploads.*` for Section 6 CSV ingestion.

---

## 6. Security & Governance Architecture

1. **Protocol-Level Read-Only Isolation**:
   - Generated SQL queries from the "Ask Your Data" engine run **exclusively** on a dedicated read-only connection (`get_readonly_engine()`).
   - Hard enforced via `-c default_transaction_read_only=on` and `-c statement_timeout=10000`.
   - Modifying statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, etc.) are prohibited by the PostgreSQL transaction manager itself.
2. **Credential Sanitization**:
   - Database passwords, hostnames, and connection strings are never exposed in UI error banners, logs, or traces.
   - All database exceptions are sanitized before reaching the user interface.
3. **Multi-Stage Query Gatekeeping**:
   - AST / Lexical parsing (`sqlparse`) validates single-statement read-only grammar.
   - Server-side query planning validation (`EXPLAIN`) checks schema references before execution.
   - Explicit human approval (**"Approve & Run"**) is required before any query is dispatched to PostgreSQL.
4. **Secrets Management**:
   - `secrets.toml` is never committed to Git.
   - `.gitignore` rigorously excludes `.env`, `scratch/`, `.venv/`, and `*.log`.
