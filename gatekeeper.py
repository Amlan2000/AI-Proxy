import json
import re
import requests
import os
from mitmproxy import http

TEST_MODE = os.environ.get("TEST_MODE", "true").lower() == "true"  # Set to false in production

SENSITIVE_PATTERNS = {
    "OpenAI Key": r"sk-[a-zA-Z0-9-]{20,}",
    "GitHub Token": r"ghp_[a-zA-Z0-9]{36}",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Generic Secret": r"(?i)(password|secret|passwd|db_password)\s*[:=]\s*['\"][^'\"]+['\"]"
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
            f"STRICT POLICY: {policy}\n"
            f"Analyze this request. Reply 'BLOCK: [reason]' if it violates policy, or has any sensitive content or protected information, otherwise reply 'ALLOW'.\n"
            f"User request: {truncated_content}"
        )
        
        res = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": "llama3.2:1b", "prompt": system_prompt, "stream": False}, 
            timeout=3
        )
        return res.json().get("response", "").strip()
    except Exception as e:
        return "ALLOW"


def make_mock_response(user_intent: str) -> dict:
    """Returns a fake Copilot-style OpenAI chat completion response."""
    return {
        "id": "mock-chatcmpl-testmode",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        f"[TEST MODE — not a real Copilot response]\n\n"
                        f"Your request was ALLOWED by the proxy.\n"
                        f"Intent received: {user_intent[:200]}"
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def block_request(flow, reason):
    print(f"🛡️ [BLOCKED] {reason}")
    flow.response = http.Response.make(
        403,
        json.dumps({"error": "Policy Violation", "reason": reason}),
        {"Content-Type": "application/json"},
    )



def request(flow: http.HTTPFlow) -> None:
    relevant_paths = ["/chat/completions", "/completions", "/messages","responses"]
    
    print(f"\n{'='*50}")
    print(f"URL: {flow.request.pretty_url}")
    print(f"PATH: {flow.request.path}")
    print(f"METHOD: {flow.request.method}")

    is_ai_request = any(segment in flow.request.path for segment in relevant_paths)
    print(f"IS AI REQUEST: {is_ai_request}")
    
    if not is_ai_request:
        print("⏩ Skipping (not an AI path)")
        return

    try:
        raw_text = flow.request.get_text()
        data = json.loads(raw_text)
        print(f"BODY KEYS: {list(data.keys())}")


        user_intent = extract_meaningful_content(data)

        print(f"USER INTENT: {str(user_intent)[:200] if user_intent else 'None ❌'}")
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

            # Phase 3: ALLOW
            if TEST_MODE:
                print("✅ [TEST MODE] Returning mock response.")
                mock = make_mock_response(user_intent)
                flow.response = http.Response.make(
                    200,
                    json.dumps(mock),
                    {"Content-Type": "application/json"},
                )
                # Setting flow.response stops mitmproxy from forwarding — no quota used

    except json.JSONDecodeError:
        pass