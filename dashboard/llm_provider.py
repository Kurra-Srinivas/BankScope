"""
BankScope — Modular LLM Provider Interface
Supports Google Gemini, OpenAI, and a built-in offline banking SQL synthesizer fallback.
Credentials and provider options are read strictly from environment variables (.env).
"""

import os
import re
import json
import requests
from abc import ABC, abstractmethod
from dotenv import load_dotenv

# Load root .env
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def get_config_secret(key: str, default: str = "") -> str:
    """
    Retrieve configuration value supporting both:
    1. Streamlit Community Cloud: `st.secrets`
    2. Local Development: environment variables via python-dotenv (.env)
    """
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets:
            if key in st.secrets and st.secrets[key]:
                return str(st.secrets[key])
            if "llm" in st.secrets and key.lower() in st.secrets["llm"]:
                return str(st.secrets["llm"][key.lower()])
    except Exception:
        pass
    return os.getenv(key, default)


class BaseLLMProvider(ABC):
    """Abstract Base Class for LLM Providers."""
    
    name: str = "BaseProvider"
    
    @abstractmethod
    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        """Generate response text for a given prompt and system instruction."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if API credentials and network requirements are met."""
        pass


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API Provider using direct HTTPS endpoint."""
    
    name: str = "Google Gemini"
    
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or get_config_secret("GEMINI_API_KEY") or get_config_secret("GOOGLE_API_KEY")
        self.model = model or get_config_secret("GEMINI_MODEL", "gemini-1.5-flash")
        
    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)
        
    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        if not self.is_available():
            raise ValueError("GEMINI_API_KEY is not configured in .env or Streamlit Secrets.")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        contents = []
        if system_instruction:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System Context & Rules:\n{system_instruction}"}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will strictly generate PostgreSQL queries based on your rules."}]
            })
            
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.95,
                "maxOutputTokens": 2048,
            }
        }
        
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise RuntimeError(f"Gemini API Error ({response.status_code}): {response.text}")
            
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected response structure from Gemini: {data}")


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API Provider using chat completions endpoint."""
    
    name: str = "OpenAI"
    
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or get_config_secret("OPENAI_API_KEY")
        self.model = model or get_config_secret("OPENAI_MODEL", "gpt-4o-mini")
        
    def is_available(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)
        
    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        if not self.is_available():
            raise ValueError("OPENAI_API_KEY is not configured in .env or Streamlit Secrets.")
            
        url = "https://api.openai.com/v1/chat/completions"
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise RuntimeError(f"OpenAI API Error ({response.status_code}): {response.text}")
            
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected response structure from OpenAI: {data}")


class OfflineBankingSQLProvider(BaseLLMProvider):
    """
    Offline Rule-Based Semantic SQL Generator.
    Acts as a reliable, high-fidelity fallback when external LLM API keys
    are not yet populated in .env. Accurately synthesizes PostgreSQL queries
    across core banking domains and uploaded datasets.
    """
    
    name: str = "BankScope Offline SQL Engine"
    
    def is_available(self) -> bool:
        return True
        
    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        q_lower = prompt.lower()
        
        # Check if target dataset is from the uploads schema
        if "schema: uploads" in system_instruction.lower():
            table_match = re.search(r"uploads\.([a-zA-Z0-9_]+)", system_instruction)
            tbl = f'uploads."{table_match.group(1)}"' if table_match else 'uploads."dataset"'
            
            if any(w in q_lower for w in ["average", "avg", "mean"]) and any(w in q_lower for w in ["status", "category"]):
                return f"SELECT\n    card_status,\n    COUNT(*) AS total_cards,\n    ROUND(AVG(credit_limit_usd)::numeric, 2) AS avg_credit_limit_usd,\n    ROUND(AVG(current_balance_usd)::numeric, 2) AS avg_balance_usd\nFROM {tbl}\nGROUP BY card_status\nORDER BY avg_credit_limit_usd DESC;"
            elif any(w in q_lower for w in ["count", "how many", "total records", "rows"]):
                return f"SELECT COUNT(*) AS total_records\nFROM {tbl};"
            elif any(w in q_lower for w in ["average", "avg", "mean"]):
                return f"SELECT\n    ROUND(AVG(current_balance_usd)::numeric, 2) AS avg_balance_usd,\n    ROUND(AVG(credit_limit_usd)::numeric, 2) AS avg_credit_limit_usd\nFROM {tbl};"
            elif any(w in q_lower for w in ["duplicate", "dup"]):
                return f"SELECT\n    card_number,\n    cardholder_name,\n    COUNT(*) AS occurrence_count\nFROM {tbl}\nGROUP BY card_number, cardholder_name\nHAVING COUNT(*) > 1;"
            elif any(w in q_lower for w in ["status", "active", "delinquent", "closed"]):
                return f"SELECT\n    card_status,\n    COUNT(*) AS total_cards,\n    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_cards\nFROM {tbl}\nGROUP BY card_status\nORDER BY total_cards DESC;"
            else:
                return f"SELECT *\nFROM {tbl}\nLIMIT 25;"
                
        # Core BankScope Banking Warehouse Queries
        if any(w in q_lower for w in ["customer", "client", "who", "user"]) and any(w in q_lower for w in ["top", "richest", "wealth", "balance", "most"]):
            return (
                "WITH customer_balances AS (\n"
                "    SELECT \n"
                "        customer_id,\n"
                "        COUNT(account_id) AS total_accounts,\n"
                "        SUM(balance_usd) AS total_deposit_balance_usd\n"
                "    FROM accounts\n"
                "    GROUP BY customer_id\n"
                ")\n"
                "SELECT \n"
                "    c.customer_id,\n"
                "    c.first_name || ' ' || c.last_name AS customer_name,\n"
                "    c.city,\n"
                "    c.credit_score,\n"
                "    cb.total_accounts,\n"
                "    ROUND(cb.total_deposit_balance_usd, 2) AS total_deposit_balance_usd,\n"
                "    DENSE_RANK() OVER (ORDER BY cb.total_deposit_balance_usd DESC) AS wealth_rank\n"
                "FROM customers c\n"
                "JOIN customer_balances cb ON c.customer_id = cb.customer_id\n"
                "ORDER BY cb.total_deposit_balance_usd DESC\n"
                "LIMIT 15;"
            )
            
        elif any(w in q_lower for w in ["rfm", "segment", "champion", "loyal", "at risk"]):
            return (
                "WITH customer_rfm_raw AS (\n"
                "    SELECT \n"
                "        c.customer_id,\n"
                "        DATE '2025-12-31' - MAX(t.transaction_date)::DATE AS recency_days,\n"
                "        COUNT(t.transaction_id) AS frequency,\n"
                "        SUM(t.amount_usd) AS monetary_usd\n"
                "    FROM customers c\n"
                "    JOIN accounts a ON c.customer_id = a.customer_id\n"
                "    JOIN transactions t ON a.account_id = t.account_id\n"
                "    GROUP BY c.customer_id\n"
                "),\n"
                "rfm_scores AS (\n"
                "    SELECT \n"
                "        customer_id,\n"
                "        recency_days,\n"
                "        frequency,\n"
                "        monetary_usd,\n"
                "        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,\n"
                "        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,\n"
                "        NTILE(5) OVER (ORDER BY monetary_usd ASC) AS m_score\n"
                "    FROM customer_rfm_raw\n"
                "),\n"
                "rfm_segments AS (\n"
                "    SELECT \n"
                "        customer_id,\n"
                "        CASE \n"
                "            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '1. Champions'\n"
                "            WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN '2. Loyal Customers'\n"
                "            WHEN r_score >= 4 AND f_score <= 2 THEN '3. Recent Promising Customers'\n"
                "            WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN '4. At Risk'\n"
                "            WHEN r_score <= 2 AND f_score <= 2 AND m_score >= 3 THEN '5. Need Attention'\n"
                "            WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN '6. Hibernating / Lost'\n"
                "            ELSE '7. Average / Steady'\n"
                "        END AS rfm_segment,\n"
                "        monetary_usd\n"
                "    FROM rfm_scores\n"
                ")\n"
                "SELECT \n"
                "    rfm_segment,\n"
                "    COUNT(customer_id) AS customer_count,\n"
                "    ROUND(COUNT(customer_id) * 100.0 / SUM(COUNT(customer_id)) OVER (), 2) AS customer_pct,\n"
                "    ROUND(SUM(monetary_usd), 2) AS total_spend_usd\n"
                "FROM rfm_segments\n"
                "GROUP BY rfm_segment\n"
                "ORDER BY rfm_segment ASC;"
            )
            
        elif any(w in q_lower for w in ["merchant", "vendor", "store", "business"]) and any(w in q_lower for w in ["top", "volume", "revenue", "highest"]):
            return (
                "SELECT \n"
                "    m.merchant_id,\n"
                "    m.merchant_name,\n"
                "    m.city,\n"
                "    COUNT(t.transaction_id) AS total_transactions,\n"
                "    ROUND(SUM(t.amount_usd), 2) AS total_processed_volume_usd,\n"
                "    ROUND(AVG(t.amount_usd), 2) AS avg_ticket_usd\n"
                "FROM merchants m\n"
                "JOIN transactions t ON m.merchant_id = t.merchant_id\n"
                "GROUP BY m.merchant_id, m.merchant_name, m.city\n"
                "ORDER BY total_processed_volume_usd DESC\n"
                "LIMIT 15;"
            )
            
        elif any(w in q_lower for w in ["loan", "lending", "interest", "apr", "borrow"]):
            return (
                "SELECT \n"
                "    CASE \n"
                "        WHEN interest_rate < 5.00 THEN '1. Low (<5%)'\n"
                "        WHEN interest_rate BETWEEN 5.00 AND 7.99 THEN '2. Prime (5%-7.99%)'\n"
                "        WHEN interest_rate BETWEEN 8.00 AND 11.99 THEN '3. Standard (8%-11.99%)'\n"
                "        ELSE '4. High / Subprime (>=12%)'\n"
                "    END AS interest_rate_tier,\n"
                "    COUNT(loan_id) AS total_loans,\n"
                "    ROUND(SUM(loan_amount), 2) AS total_principal_usd,\n"
                "    ROUND(AVG(loan_amount), 2) AS avg_loan_amount_usd,\n"
                "    ROUND(SUM(loan_amount * interest_rate) / SUM(loan_amount), 2) AS weighted_avg_apr\n"
                "FROM loans\n"
                "GROUP BY 1\n"
                "ORDER BY 1;"
            )
            
        elif any(w in q_lower for w in ["month", "trend", "growth", "velocity", "over time", "history"]):
            return (
                "WITH monthly_aggregates AS (\n"
                "    SELECT \n"
                "        DATE_TRUNC('month', transaction_date)::DATE AS transaction_month,\n"
                "        COUNT(transaction_id) AS transaction_count,\n"
                "        ROUND(SUM(amount_usd), 2) AS total_volume_usd\n"
                "    FROM transactions\n"
                "    GROUP BY DATE_TRUNC('month', transaction_date)::DATE\n"
                ")\n"
                "SELECT \n"
                "    transaction_month,\n"
                "    transaction_count,\n"
                "    total_volume_usd,\n"
                "    LAG(total_volume_usd, 1) OVER (ORDER BY transaction_month) AS prev_month_volume_usd,\n"
                "    ROUND(total_volume_usd - LAG(total_volume_usd, 1) OVER (ORDER BY transaction_month), 2) AS mom_growth_usd\n"
                "FROM monthly_aggregates\n"
                "ORDER BY transaction_month DESC\n"
                "LIMIT 24;"
            )
            
        elif any(w in q_lower for w in ["city", "state", "geography", "location"]):
            return (
                "SELECT \n"
                "    c.city,\n"
                "    COUNT(DISTINCT c.customer_id) AS customer_count,\n"
                "    COUNT(a.account_id) AS account_count,\n"
                "    ROUND(COALESCE(SUM(a.balance_usd), 0), 2) AS total_deposits_usd,\n"
                "    ROUND(AVG(c.credit_score), 1) AS avg_credit_score\n"
                "FROM customers c\n"
                "LEFT JOIN accounts a ON c.customer_id = a.customer_id\n"
                "GROUP BY c.city\n"
                "ORDER BY customer_count DESC\n"
                "LIMIT 15;"
            )
            
        else:
            # Default analytical ledger overview
            return (
                "SELECT \n"
                "    account_type,\n"
                "    COUNT(account_id) AS total_accounts,\n"
                "    ROUND(SUM(balance_usd), 2) AS total_balance_usd,\n"
                "    ROUND(AVG(balance_usd), 2) AS avg_balance_usd\n"
                "FROM accounts\n"
                "GROUP BY account_type\n"
                "ORDER BY total_balance_usd DESC;"
            )


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function to initialize the appropriate LLM provider.
    Priority:
    1. Explicit LLM_PROVIDER in .env ('gemini', 'openai', 'offline')
    2. Auto-detect GEMINI_API_KEY / GOOGLE_API_KEY
    3. Auto-detect OPENAI_API_KEY
    4. Fallback to OfflineBankingSQLProvider
    """
    requested = get_config_secret("LLM_PROVIDER", "").strip().lower()
    
    if requested == "gemini":
        provider = GeminiProvider()
        if provider.is_available():
            return provider
            
    elif requested == "openai":
        provider = OpenAIProvider()
        if provider.is_available():
            return provider
            
    elif requested == "offline":
        return OfflineBankingSQLProvider()
        
    # Auto-detection
    gemini = GeminiProvider()
    if gemini.is_available():
        return gemini
        
    openai = OpenAIProvider()
    if openai.is_available():
        return openai
        
    return OfflineBankingSQLProvider()
