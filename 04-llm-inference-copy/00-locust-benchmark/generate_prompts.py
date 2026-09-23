#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Isac Pasianotto <isac.pasianotto@phd.units.it>
# SPDX-FileCopyrightText: 2026 Niccolo Tosato <niccolo.tosato@phd.units.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Generate IT interview questions and save them to prompt.txt."""

import os
import random
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_HOST = "https://127.0.0.1/vllm"
DEFAULT_ENDPOINT = "/v1/chat/completions"

DEFAULT_TOKEN = "CHANGE WITH YOUR PROPER TOKEN"

MODEL_ID = "openai/gpt-oss-120b"
HOST = DEFAULT_HOST
ENDPOINT = DEFAULT_ENDPOINT
OUTPUT_FILE = "prompt.txt"

# Token limits for each request (min and max)
TOKEN_MIN = 50
TOKEN_MAX = 300


def main(count=200):
    token = os.getenv("JWT_TOKEN", DEFAULT_TOKEN)
    questions = []
    
    print(f"Generating {count} IT interview questions from {MODEL_ID}...")
    print(f"Token range per request: {TOKEN_MIN} - {TOKEN_MAX}")
    
    for i in range(1, count + 1):
        prompt = "Generate exactly one IT interview question for a software engineer candidate. Return only the question, no numbering, no explanation."
        
        max_tokens = random.randint(TOKEN_MIN, TOKEN_MAX)
        
        payload = {
            "model": MODEL_ID,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 1.0,
        }
        
        try:
            response = requests.post(
                f"{HOST}{ENDPOINT}",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=120,
                verify=False,
            )
            response.raise_for_status()
            
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
            if content:
                questions.append(content)
                print(f"  [{i}/{count}] (tokens={max_tokens}) Generated: {content[:70]}...")
            else:
                print(f"  [{i}/{count}] ERROR: Empty response")
        except Exception as e:
            print(f"  [{i}/{count}] ERROR: {e}")
    
    if not questions:
        print("ERROR: No questions generated.")
        return 1
    
    print(f"\nSaving {len(questions)} questions to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for question in questions:
            f.write(question + "\n")
    
    print(f"Done. Saved {len(questions)} questions to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
