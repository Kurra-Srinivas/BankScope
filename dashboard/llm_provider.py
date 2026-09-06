"""
BankScope — Modular LLM Provider Interface
Supports Groq (Primary), Google Gemini, OpenAI, and a built-in offline rule-based demo engine.
Credentials and provider options are read securely from Streamlit st.secrets (cloud) or .env (local).
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
    1. Streamlit Community Cloud: `st.secrets` (flat keys and [llm]/[groq] sections)
    2. Local Development: environment variables via python-dotenv (.env)
    """
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets:
            if key in st.secrets and st.secrets[key]:
                return str(st.secrets[key])
            if "llm" in st.secrets and key.lower() in st.secrets["llm"]:
                return str(st.secrets["llm"][key.lower()])
            if "groq" in st.secrets and key.lower() in st.secrets["groq"]:
                return str(st.secrets["groq"][key.lower()])
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


class GroqProvider(BaseLLMProvider):
    """
    Groq AI Provider using OpenAI-compatible HTTPS endpoint.
    Primary high-throughput LLM provider for BankScope.
    Endpoint: https://api.groq.com/openai/v1/chat/completions
    Default model: openai/gpt-oss-20b
    """
    
    name: str = "Groq"
    
    def __init__(self, api_key: str = None, model: str = None):
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = get_config_secret("GROQ_API_KEY").strip()
        self.model = model or get_config_secret("GROQ_MODEL", "openai/gpt-oss-20b")
        base_url = get_config_secret("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        self.endpoint = f"{base_url}/chat/completions"
        
    def is_available(self) -> bool:
        if not self.api_key or len(self.api_key) <= 8:
            return False
        # Filter out placeholders and example keys
        placeholder_indicators = ["your_", "placeholder", "xxx", "<", "replace"]
        if any(ind in self.api_key.lower() for ind in placeholder_indicators):
            return False
        return True
        
    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        if not self.is_available():
            raise ValueError("GROQ_API_KEY is not configured in Streamlit Secrets or .env.")
            
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
        response = requests.post(self.endpoint, json=payload, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise RuntimeError(f"Groq API Error ({response.status_code}): {response.text}")
            
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected response structure from Groq: {data}")


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API Provider using direct HTTPS endpoint."""
    
    name: str = "Google Gemini"
    def __init__(self, api_key: str = None, model: str = None):
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = (get_config_secret("GEMINI_API_KEY") or get_config_secret("GOOGLE_API_KEY")).strip()
        self.model = model or get_config_secret("GEMINI_MODEL", "gemini-2.0-flash")
        
    def is_available(self) -> bool:
        if not self.api_key or len(self.api_key) <= 10:
            return False
        placeholder_indicators = ["your_", "placeholder", "xxx", "<", "replace"]
        if any(ind in self.api_key.lower() for ind in placeholder_indicators):
            return False
        return True
        
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
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = get_config_secret("OPENAI_API_KEY").strip()
        self.model = model or get_config_secret("OPENAI_MODEL", "gpt-4o-mini")
        
    def is_available(self) -> bool:
        if not self.api_key or len(self.api_key) <= 10:
            return False
        placeholder_indicators = ["your_", "placeholder", "xxx", "<", "replace"]
        if any(ind in self.api_key.lower() for ind in placeholder_indicators):
            return False
        return True

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
    Offline Rule-Based Semantic SQL Generator (Demo Mode).
    Non-AI rule-based fallback when external LLM API keys are not configured.
    Accurately synthesizes PostgreSQL queries across core banking domains and uploaded datasets.
    """
    
    name: str = "Rule-Based Demo Engine (Non-AI)"
    
    def is_available(self) -> bool:
        return True
        
    def generate_text(self, prompt: str, system_instruction: str = "") -> str:
        q_lower = prompt.lower()
        
        # Check if query targets uploaded dataset schema
        if "Schema: uploads" in system_instruction or "Target Table: `uploads." in system_instruction:
            tbl_match = re.search(r"Target Table:\s*`uploads\.([a-zA-Z0-9_]+)`", system_instruction) or re.search(r"uploads\.([a-zA-Z0-9_]+)", system_instruction)
            target_tbl = f"uploads.{tbl_match.group(1)}" if tbl_match else "uploads.dataset"
            
            if ("top" in q_lower or "highest" in q_lower) and "limit" in q_lower:
                return (
                    f"SELECT \n"
                    f"    customer_segment,\n"
                    f"    ROUND(SUM(credit_limit)::numeric, 2) AS total_credit_limit,\n"
                    f"    ROUND(AVG(credit_limit)::numeric, 2) AS avg_credit_limit\n"
                    f"FROM {target_tbl}\n"
                    f"GROUP BY customer_segment\n"
                    f"ORDER BY total_credit_limit DESC\n"
                    f"LIMIT 10;"
                )
            elif "spend" in q_lower and "status" in q_lower:
                return (
                    f"SELECT \n"
                    f"    card_status,\n"
                    f"    ROUND(SUM(monthly_spend)::numeric, 2) AS total_monthly_spend,\n"
                    f"    ROUND(AVG(monthly_spend)::numeric, 2) AS avg_monthly_spend\n"
                    f"FROM {target_tbl}\n"
                    f"GROUP BY card_status\n"
                    f"ORDER BY total_monthly_spend DESC;"
                )
            elif "utilization" in q_lower:
                where_clause = "WHERE card_type IN ('Credit', 'Debit')\n" if ("credit" in q_lower or "debit" in q_lower) else ""
                return (
                    f"SELECT \n"
                    f"    card_type,\n"
                    f"    COUNT(*) AS count,\n"
                    f"    ROUND(AVG(utilization_pct)::numeric, 4) AS avg_utilization_pct\n"
                    f"FROM {target_tbl}\n"
                    f"{where_clause}"
                    f"GROUP BY card_type\n"
                    f"ORDER BY avg_utilization_pct DESC;"
                )
            elif "percent" in q_lower or "percentage" in q_lower:
                return (
                    f"SELECT \n"
                    f"    card_status,\n"
                    f"    COUNT(*) AS card_count,\n"
                    f"    ROUND((COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ())::numeric, 2) AS percentage\n"
                    f"FROM {target_tbl}\n"
                    f"GROUP BY card_status\n"
                    f"ORDER BY card_count DESC;"
                )
            elif "segment" in q_lower or "average credit limit" in q_lower:
                return (
                    f"SELECT \n"
                    f"    customer_segment,\n"
                    f"    COUNT(*) AS card_count,\n"
                    f"    ROUND(AVG(credit_limit)::numeric, 2) AS avg_credit_limit,\n"
                    f"    ROUND(SUM(monthly_spend)::numeric, 2) AS total_monthly_spend\n"
                    f"FROM {target_tbl}\n"
                    f"GROUP BY customer_segment\n"
                    f"ORDER BY avg_credit_limit DESC;"
                )
            elif "status" in q_lower or "card_status" in q_lower:
                return (
                    f"SELECT \n"
                    f"    card_status,\n"
                    f"    COUNT(*) AS total_cards,\n"
                    f"    ROUND(AVG(credit_limit)::numeric, 2) AS avg_credit_limit,\n"
                    f"    ROUND(SUM(credit_limit)::numeric, 2) AS total_credit_limit\n"
                    f"FROM {target_tbl}\n"
                    f"GROUP BY card_status\n"
                    f"ORDER BY avg_credit_limit DESC;"
                )
            elif "limit" in q_lower or "credit limit" in q_lower:
                return (
                    f"SELECT \n"
                    f"    customer_segment,\n"
                    f"    ROUND(SUM(credit_limit)::numeric, 2) AS total_credit_limit,\n"
                    f"    ROUND(AVG(credit_limit)::numeric, 2) AS avg_credit_limit\n"
                    f"FROM {target_tbl}\n"
                    f"GROUP BY customer_segment\n"
                    f"ORDER BY total_credit_limit DESC\n"
                    f"LIMIT 10;"
                )
            else:
                return (
                    f"SELECT * \n"
                    f"FROM {target_tbl}\n"
                    f"LIMIT 50;"
                )
        
        # Core Banking Semantic Matches
        if "top" in q_lower and ("customer" in q_lower or "deposit" in q_lower or "balance" in q_lower):
            return (
                "SELECT \n"
                "    c.customer_id,\n"
                "    c.first_name || ' ' || c.last_name AS full_name,\n"
                "    c.city,\n"
                "    c.credit_score,\n"
                "    ROUND(SUM(a.balance_usd), 2) AS total_deposits_usd,\n"
                "    COUNT(a.account_id) AS total_accounts\n"
                "FROM customers c\n"
                "JOIN accounts a ON c.customer_id = a.customer_id\n"
                "GROUP BY c.customer_id, c.first_name, c.last_name, c.city, c.credit_score\n"
                "ORDER BY total_deposits_usd DESC\n"
                "LIMIT 15;"
            )
            
        elif "merchant" in q_lower or "store" in q_lower:
            return (
                "SELECT \n"
                "    m.merchant_id,\n"
                "    m.merchant_name,\n"
                "    m.city,\n"
                "    COUNT(t.transaction_id) AS total_transactions,\n"
                "    ROUND(SUM(t.amount_usd), 2) AS total_revenue_usd,\n"
                "    ROUND(AVG(t.amount_usd), 2) AS avg_transaction_usd\n"
                "FROM merchants m\n"
                "JOIN transactions t ON m.merchant_id = t.merchant_id\n"
                "GROUP BY m.merchant_id, m.merchant_name, m.city\n"
                "ORDER BY total_revenue_usd DESC\n"
                "LIMIT 10;"
            )
            
        elif "month" in q_lower or "trend" in q_lower or "timeline" in q_lower or "volume" in q_lower:
            return (
                "SELECT \n"
                "    DATE_TRUNC('month', transaction_date)::DATE AS transaction_month,\n"
                "    COUNT(transaction_id) AS transaction_count,\n"
                "    ROUND(SUM(amount_usd), 2) AS total_volume_usd,\n"
                "    ROUND(AVG(amount_usd), 2) AS avg_ticket_usd\n"
                "FROM transactions\n"
                "GROUP BY transaction_month\n"
                "ORDER BY transaction_month ASC;"
            )
            
        elif "loan" in q_lower or "borrow" in q_lower or "apr" in q_lower or "interest" in q_lower:
            return (
                "SELECT \n"
                "    CASE \n"
                "        WHEN c.credit_score >= 800 THEN '1. Exceptional (800-850)'\n"
                "        WHEN c.credit_score >= 740 THEN '2. Very Good (740-799)'\n"
                "        WHEN c.credit_score >= 670 THEN '3. Good (670-739)'\n"
                "        WHEN c.credit_score >= 580 THEN '4. Fair (580-669)'\n"
                "        ELSE '5. Poor (<580)'\n"
                "    END AS credit_tier,\n"
                "    COUNT(l.loan_id) AS total_loans,\n"
                "    ROUND(SUM(l.loan_amount), 2) AS total_borrowed_usd,\n"
                "    ROUND(AVG(l.interest_rate), 2) AS avg_apr_percent\n"
                "FROM loans l\n"
                "JOIN customers c ON l.customer_id = c.customer_id\n"
                "GROUP BY credit_tier\n"
                "ORDER BY credit_tier ASC;"
            )
            
        elif "city" in q_lower or "location" in q_lower or "geographic" in q_lower:
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
    1. Explicit LLM_PROVIDER in .env / st.secrets ('groq', 'gemini', 'openai', 'offline')
    2. Auto-detect GROQ_API_KEY (Groq is the primary LLM provider)
    3. Auto-detect GEMINI_API_KEY / GOOGLE_API_KEY
    4. Auto-detect OPENAI_API_KEY
    5. Fallback to OfflineBankingSQLProvider (clearly designated as non-AI demo mode)
    """
    requested = get_config_secret("LLM_PROVIDER", "").strip().lower()
    
    if requested == "groq":
        provider = GroqProvider()
        if provider.is_available():
            return provider
            
    elif requested == "gemini":
        provider = GeminiProvider()
        if provider.is_available():
            return provider
            
    elif requested == "openai":
        provider = OpenAIProvider()
        if provider.is_available():
            return provider
            
    elif requested == "offline":
        return OfflineBankingSQLProvider()
        
    # Auto-detection: Groq is the primary provider
    groq = GroqProvider()
    if groq.is_available():
        return groq

    gemini = GeminiProvider()
    if gemini.is_available():
        return gemini
        
    openai = OpenAIProvider()
    if openai.is_available():
        return openai
        
    return OfflineBankingSQLProvider()
