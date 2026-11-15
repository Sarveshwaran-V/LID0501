"""Configuration and ICP parameters for LID0501."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = Path(os.getenv("LID_DB_PATH", str(BASE_DIR / "lid.db")))

# App Identity
PROJECT_ID = "LID0501"
NOMENCLATURE = "LID · 05 · 01"
APP_NAME = "LID0501 Lead Engine"

# Network & Web scraping safety
DEFAULT_TIMEOUT = 12.0
USER_AGENT = "LID0501-LeadEngine/0.5 (Ethical Public Researcher; Ikaiva Studio; local-cli)"
MAX_REDIRECTS = 3

# Gemini LLM Integration (Google AI Studio)
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_BASE_URL = os.getenv(
    "GEMINI_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/models"
)

# ICP (Ideal Customer Profile) Definitions
TARGET_GEOGRAPHY = "United States"

AI_DEVTOOLS_SEGMENTS = [
    "AI Infrastructure",
    "Developer Tools",
    "AI Platform",
    "B2B SaaS",
    "B2B AI Software",
    "Data Infrastructure",
    "Machine Learning",
]

CYBERSECURITY_SEGMENTS = [
    "Cybersecurity",
    "Cloud Security",
    "Application Security",
    "Security Infrastructure",
    "Identity & Access Management",
]

ALL_TARGET_SEGMENTS = AI_DEVTOOLS_SEGMENTS + CYBERSECURITY_SEGMENTS

PREFERRED_EMPLOYEE_MIN = 15
PREFERRED_EMPLOYEE_MAX = 200

PREFERRED_STAGES = [
    "Seed",
    "Series A",
    "Series B",
    "Bootstrapped",
]

IKAIVA_SERVICES = [
    "Brand strategy",
    "Brand identity",
    "Website strategy and design",
    "Website interface design",
    "Product positioning and messaging clarity",
]

TARGET_PROJECT_VALUE = "$2,500 - $5,000+"

# Scoring Rubric Weights (Max 10 points)
MAX_SCORE = 10
SCORE_THRESHOLDS = {
    "high_priority": 8.0,
    "potentially_qualified": 7.0,
}

# Signal recency preference (days)
PREFERRED_SIGNAL_RECENCY_DAYS = 90
