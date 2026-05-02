from email import policy
import json
import re
import requests
import os
from mitmproxy import http

model = "llama3.2:1b"

TEST_MODE = os.environ.get("TEST_MODE", "true").lower() == "true"  # Set to false in production

SENSITIVE_PATTERNS = {
    "OpenAI Key": r"sk-[a-zA-Z0-9-]{20,}",
    "GitHub Token": r"ghp_[a-zA-Z0-9]{36}",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Generic Secret": r"(?i)(password|secret|passwd|db_password|pwd)\s*[:=\s]\s*[a-zA-Z0-9!@#$%^&*]{4,}"    # Can add more sensetive patterns here
}

os.environ["NO_PROXY"] = "127.0.0.1,localhost"

def extract_meaningful_content(data):
    if "messages" in data and isinstance(data["messages"], list):
        user_messages = [m for m in data["messages"] if m.get("role") == "user"]
        if user_messages:
            content = user_messages[-1].get("content", "")
            if isinstance(content, list):
                content = " ".join([item.get("text", "") for item in content if isinstance(item, dict)])
            content = str(content)

            match = re.search(r"<userRequest>(.*?)</userRequest>", content, re.DOTALL)
            if match:
                return match.group(1).strip()

            match = re.search(r"<user_query>(.*?)</user_query>", content, re.DOTALL)
            if match:
                return match.group(1).strip()

            return content.strip()
        return None

    if "input" in data and isinstance(data["input"], list):
        user_messages = [item for item in data["input"] if isinstance(item, dict) and item.get("role") == "user"]
        if user_messages:
            content = user_messages[-1].get("content", "")
            if isinstance(content, list):
                content = " ".join([item.get("text", "") for item in content if isinstance(item, dict)])
            content = str(content)

            match = re.search(r"<userRequest>(.*?)</userRequest>", content, re.DOTALL)
            if match:
                return match.group(1).strip()

            match = re.search(r"<user_query>(.*?)</user_query>", content, re.DOTALL)
            if match:
                return match.group(1).strip()

            return content.strip()
        return None  

    if "prediction" in data and isinstance(data["prediction"], dict):
        return data["prediction"].get("content", "").strip()

    if "prompt" in data:
        return str(data["prompt"])[-500:].strip()

    return None


def ask_local_agent(content):
    try:
        # print("inside local LLM Layer"+content)
        policy = "Do not allow sharing of internal project names or credentials."
        if os.path.exists("instructions.md"):
            with open("instructions.md", "r") as f:
                policy = f.read()

        truncated_content = content[:2000] 

        system_prompt = (
            f"### SYSTEM POLICY: {policy}\n"
            f"### TASK: Analyze the user request for secrets or policy violations.\n"
            f"### OUTPUT RULE: You MUST reply with ONLY one word: 'ALLOW' or 'BLOCK'. Do not explain.\n"
            f"### USER REQUEST: {content[:1000]}"
        )
        
        res = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model, "prompt": system_prompt, "stream": False}, 
            timeout=3
        )

        decision = res.json().get("response", "").strip().upper()
        if "ALLOW" in decision:
            return "ALLOW"

        return "BLOCK"

    except Exception as e:
        return "ALLOW"



def block_request(flow, reason):
    print(f"[BLOCKED] {reason}")
    flow.response = http.Response.make(
        403,
        json.dumps({"error": "Policy Violation", "reason": reason}),
        {"Content-Type": "application/json"},
    )



def request(flow: http.HTTPFlow) -> None:
    relevant_paths = ["/chat/completions", "/completions", "/messages","responses"]
    
    # print(f"\n{'='*50}")
    # print(f"URL: {flow.request.pretty_url}")
    # print(f"PATH: {flow.request.path}")

    is_ai_request = any(segment in flow.request.path for segment in relevant_paths)
    # print(f"IS AI REQUEST: {is_ai_request}")
    
    if not is_ai_request:
        # print("Skipping (not an AI path)")
        return
    
    print(f"\n{'='*50}")
    print(f"URL: {flow.request.pretty_url}")
    print(f"PATH: {flow.request.path}")

    try:
        raw_text = flow.request.get_text()
        data = json.loads(raw_text)
        # print(f"BODY KEYS: {list(data.keys())}")


        user_intent = extract_meaningful_content(data)

        print(f"USER INTENT: {str(user_intent)[:200] if user_intent else 'None'}")
        print(f"TEST_MODE: {TEST_MODE}")

        if user_intent:
            # Phase 1: Regex check
            for label, pattern in SENSITIVE_PATTERNS.items():
                if re.search(pattern, user_intent):
                    block_request(flow, f"Regex Match in Query: {label}")
                    return

            # Phase 2: LLM agent check
            decision = ask_local_agent(user_intent) 
            print(f"LLM Decision: {decision}")
            if "BLOCK" in decision.upper():
                block_request(flow, decision)
                return

            # Phase 3: Accept mock request
            if TEST_MODE:
                print("[TEST MODE] Copilot mock request went through.")
                flow.response = http.Response.make(
                    200,
                    {"Content-Type": "application/json"},
                )

    except json.JSONDecodeError:
        pass