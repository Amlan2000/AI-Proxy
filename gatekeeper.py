import json
import re
import requests
import os
from mitmproxy import http

# --- CONFIGURATION ---
SENSITIVE_PATTERNS = {
    "OpenAI Key": r"sk-[a-zA-Z0-9]{6,}",
    "GitHub Token": r"ghp_[a-zA-Z0-9]{36}",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Generic Secret": r"(?i)(password|secret|passwd|db_password)\s*[:=]\s*['\"][^'\"]+['\"]"
}

os.environ["NO_PROXY"] = "127.0.0.1,localhost"

def extract_meaningful_content(data):
    """
    Parses the messy Copilot JSON to find what the user actually wants.
    Handles both Chat (<user_query>) and Inline (prediction).
    """
    # 1. Check for Chat Style (Messages array)
    if "messages" in data and isinstance(data["messages"], list):
        # Filter for messages where role is user
        user_messages = [m for m in data["messages"] if m.get("role") == "user"]
            
        if user_messages:
            # Pick the absolute last user object (as seen in your screenshot)
            last_user_obj = user_messages[-1]
            content = last_user_obj.get("content", "")
            print("Extracted raw content from chat completions messages: "+str(content)[:200].strip())

            # Handle list-based content if it's multimodal
            if isinstance(content, list):
                content = " ".join([item.get("text", "") for item in content if isinstance(item, dict)])
                
            # Now, use regex to pull ONLY what is inside the <user_query> tags
            query_match = re.search(r"<user_query>(.*?)</user_query>", str(content), re.DOTALL)
                
            if query_match:
                extracted_query = query_match.group(1).strip()
                print(f"✅ Clean Query Extracted: {extracted_query}")
                return extracted_query
                
            # If tags aren't found, we check for internal summary noise before falling back
            internal_keywords = ["Summarize the following", "OUTPUT FORMAT:", "GENERAL:"]
            if any(k in str(content) for k in internal_keywords):
                return None     
            
        return str(content).strip()

    # 2. Check for Inline Completion Style (Prediction key)
    if "prediction" in data and isinstance(data["prediction"], dict):
        print("Extracted user query from chat completions predictions: "+data["prediction"].get("content", "").strip())
        return data["prediction"].get("content", "").strip()
    
    # 3. Check for legacy prompt style
    if "prompt" in data:
        # If prompt is a massive string, we just take the last 500 chars 
        # as that's usually where the new user typing is
        print("Extracted user query from chat completions prompt: "+str(data["prompt"])[-500:].strip())
        return str(data["prompt"])[-500:].strip()

    return None

def ask_local_agent(content):
    try:
        # Try to load policy, fallback if file missing
        print("inside local LLM Layer"+content)
        policy = "Do not allow sharing of internal project names or credentials."
        if os.path.exists("instructions.md"):
            with open("instructions.md", "r") as f:
                policy = f.read()

        # Clean content: if it's JSON, Llama 1B handles it better as a string 
        # but we should trim it if it's massive.
        truncated_content = content[:2000] 

        system_prompt = (
            f"STRICT POLICY: {policy}\n"
            f"Analyze this request. Reply 'BLOCK: [reason]' if it violates policy, or has any sensitive content or protected information, otherwise reply 'ALLOW'.\n"
            f"User request: {truncated_content}"
        )
        
        res = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": "llama3.2:1b", "prompt": system_prompt, "stream": False}, 
            timeout=3 # Keep timeout short for UX
        )
        return res.json().get("response", "").strip()
    except Exception as e:
        # print(f"⚠️ Security Layer Bypass (Error): {e}")
        return "ALLOW"

def request(flow: http.HTTPFlow) -> None:
    relevant_paths = ["/chat/completions", "/completions", "/messages"]
    if not any(p in flow.request.path for p in flow.request.pretty_url):
        return

    try:
        raw_text = flow.request.get_text()
        data = json.loads(raw_text)
        
        # --- NEW FLOW: EXTRACT FIRST ---
        user_intent = extract_meaningful_content(data)

        if user_intent:
            print(f"🔍 Checking Intent: {user_intent[:100]}...")

            # --- PHASE 1: REGEX (Only on extracted intent) ---
            for label, pattern in SENSITIVE_PATTERNS.items():
                if re.search(pattern, user_intent):
                    block_request(flow, f"Regex Match in Query: {label}")
                    return

            # --- PHASE 2: LLM AGENT ---
            decision = ask_local_agent(user_intent)
            print(f"LLM Decision: {decision}")
            if "BLOCK" in decision.upper():
                block_request(flow, decision)
                
    except json.JSONDecodeError:
        pass



def block_request(flow, reason):
    print(f"🛡️ [BLOCKED] {reason}")
    flow.response = http.Response.make(
        403, 
        json.dumps({"error": "Policy Violation", "reason": reason}),
        {"Content-Type": "application/json"}
    )