"""Configuration settings for CentrAlign Autonomous AI Task Worker."""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Automatically load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM Settings
    llm_provider: str = Field(default="deterministic", alias="LLM_PROVIDER")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-flash", alias="GEMINI_MODEL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Guardrails and Reliability
    agent_max_steps: int = Field(default=12, alias="AGENT_MAX_STEPS")
    high_value_approval_threshold: float = Field(default=5000.0, alias="HIGH_VALUE_APPROVAL_THRESHOLD")
    max_tool_retries: int = Field(default=3, alias="MAX_TOOL_RETRIES")
    strict_independent_verification: bool = Field(default=True, alias="STRICT_INDEPENDENT_VERIFICATION")

    # Environment Paths
    sandbox_dir: Path = Field(default=BASE_DIR / "data" / "company_files", alias="SANDBOX_DIR")
    erp_db_path: Path = Field(default=BASE_DIR / "data" / "company_erp.db", alias="ERP_DB_PATH")


settings = Settings()

# Ensure directories exist
settings.sandbox_dir.mkdir(parents=True, exist_ok=True)
settings.erp_db_path.parent.mkdir(parents=True, exist_ok=True)
