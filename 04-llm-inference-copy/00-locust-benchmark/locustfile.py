# SPDX-FileCopyrightText: 2026 Isac Pasianotto <isac.pasianotto@phd.units.it>
# SPDX-FileCopyrightText: 2026 Niccolo Tosato <niccolo.tosato@phd.units.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Multi-Model LLM Stress Testing with Locust
------------------------------------------
One locust run = one model, selected via MODEL_NAME env var.
Experiment bookkeeping (START/END) and per-request token usage are
logged.

Run example (one model, headless):
  MODEL_NAME="Llama-4-Scout-17B" locust -f locustfile.py --headless -u 4 -r 1 --run-time 5m
"""

import logging
import os
import random
import uuid as _uuid

import urllib3

import requests as _requests
from locust import HttpUser, between, events, task

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------

JWT_TOKEN = os.getenv(
    "JWT_TOKEN")

MODEL_NAME        = os.getenv("MODEL_NAME")          # REQUIRED
SLURM_JOB_ID      = os.getenv("SLURM_JOB_ID",      "local")
SLURM_JOB_NODELIST= os.getenv("SLURM_JOB_NODELIST","localhost")
PROMPT_FILE       = os.getenv("PROMPT_FILE",        "prompt.txt")

# Benchmark token caps are randomized per request within this range.
TOKEN_MIN = 1000
TOKEN_MAX = 2000

if TOKEN_MIN > TOKEN_MAX:
    raise ValueError(f"Invalid token range: TOKEN_MIN ({TOKEN_MIN}) > TOKEN_MAX ({TOKEN_MAX})")


def _pick_max_tokens() -> int:
    return random.randint(TOKEN_MIN, TOKEN_MAX)

# ---------------------------------------------------------------------------
# Model catalogue
# ---------------------------------------------------------------------------

MODELS = [

    {
        "name": "GPT-OSS-120B",
        "host": "https://127.0.0.1/vllm",
        "endpoint": "/v1/chat/completions",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {JWT_TOKEN}",
        },
        "payload": lambda prompt: {
            "model": "openai/gpt-oss-120b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _pick_max_tokens(),
        },
        "weight": 1,
    },
    {
        "name": "Qwen3-VL-235B-Thinking",
        "host": "https://127.0.0.1/vllm",
        "endpoint": "/v1/chat/completions",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {JWT_TOKEN}",
        },
        "payload": lambda prompt: {
            "model": "Qwen/Qwen3-VL-235B-A22B-Thinking-FP8",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _pick_max_tokens(),
        },
        "weight": 1,
    },
    {
        "name": "Llama-4-Scout-17B",
        "host": "https://127.0.0.1/vllm",
        "endpoint": "/v1/chat/completions",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {JWT_TOKEN}",
        },
        "payload": lambda prompt: {
            "model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _pick_max_tokens(),
        },
        "weight": 1,
    },
]

# ---------------------------------------------------------------------------
# Select the active model for this run (mandatory)
# ---------------------------------------------------------------------------

if not MODEL_NAME:
    raise ValueError(
        "MODEL_NAME environment variable is required. "
        f"Available models: {[m['name'] for m in MODELS]}"
    )

ACTIVE_MODEL = next((m for m in MODELS if m["name"] == MODEL_NAME), None)
if ACTIVE_MODEL is None:
    raise ValueError(
        f"MODEL_NAME='{MODEL_NAME}' not found in MODELS catalogue. "
        f"Available: {[m['name'] for m in MODELS]}"
    )

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

DEFAULT_PROMPTS = [
    "Explain Kubernetes architecture in depth, including components, networking, and deployment strategies.",
    "Write a Python module with multiple functions that reverse strings, handle Unicode, and include unit tests and docstrings.",
    "Provide a comprehensive report on the impact of AI on healthcare, covering ethics, regulations, economics, and case studies.",
    "Generate detailed marketing copy for a fintech startup, including product positioning, target audience analysis, and multiple tagline options.",
]


def _load_prompts(path: str) -> list[str]:
    """
    Load prompts from a text file (one prompt per line).
    Falls back to DEFAULT_PROMPTS if the file is missing, unreadable, or empty.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            prompts = [line.strip() for line in fh if line.strip()]
    except OSError as exc:
        print(
            f"Prompt file '{path}' unavailable ({exc}). "
            f"Falling back to {len(DEFAULT_PROMPTS)} built-in prompts."
        )
        return DEFAULT_PROMPTS

    if not prompts:
        print(
            f"Prompt file '{path}' is empty. "
            f"Falling back to {len(DEFAULT_PROMPTS)} built-in prompts."
        )
        return DEFAULT_PROMPTS

    print(f"Loaded {len(prompts)} prompts from '{path}'.")
    return prompts


PROMPTS = _load_prompts(PROMPT_FILE)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    filename="llm_errors.log",
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Experiment lifecycle tracking (module-level, set once at test_start)
# ---------------------------------------------------------------------------

EXPERIMENT_ID: str = ""


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global EXPERIMENT_ID
    EXPERIMENT_ID = str(_uuid.uuid4())
    logging.info(
        "Experiment START | id=%s | model=%s | job=%s | nodes=%s",
        EXPERIMENT_ID, ACTIVE_MODEL["name"], SLURM_JOB_ID, SLURM_JOB_NODELIST,
    )


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    logging.info(
        "Experiment END | id=%s | model=%s",
        EXPERIMENT_ID, ACTIVE_MODEL["name"],
    )


# ---------------------------------------------------------------------------
# Generic request-failure logger (Locust v2+ compatible)
# ---------------------------------------------------------------------------

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    if exception:
        log.error("FAIL | %s | %s | %.0fms | %s", name, request_type, response_time, exception)


# ---------------------------------------------------------------------------
# Locust user
# ---------------------------------------------------------------------------

class MultiModelUser(HttpUser):
    wait_time = between(1, 2)
    connection_timeout = 60   # seconds to establish connection
    network_timeout = 180     # seconds waiting for full response
    host = ACTIVE_MODEL["host"]

    def on_start(self):
        self.client.verify = False

    @task
    def run_benchmark(self):
        prompt = random.choice(PROMPTS)
        payload = ACTIVE_MODEL["payload"](prompt)
        request_max_tokens = payload.get("max_tokens", 0)

        with self.client.post(
            ACTIVE_MODEL["endpoint"],
            json=payload,
            headers=ACTIVE_MODEL["headers"],
            name=f"{ACTIVE_MODEL['name']} Request",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(
                    f"{ACTIVE_MODEL['name']} failed: {response.status_code} {response.text[:120]}"
                )
                return

            try:
                data = response.json()
            except Exception as exc:
                response.failure(f"JSON decode error: {exc}")
                return

            usage = data.get("usage", {})
            prompt_tokens     = usage.get("prompt_tokens",     0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens      = usage.get("total_tokens",      0)

            print(
                f"{ACTIVE_MODEL['name']} | "
                f"max_tokens={request_max_tokens} | "
                f"prompt={prompt_tokens} completion={completion_tokens} total={total_tokens} tokens | "
                f"{response.elapsed.total_seconds():.2f}s"
            )
