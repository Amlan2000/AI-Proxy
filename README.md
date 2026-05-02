# AI Gatekeeper

A local security proxy that sits between your AI coding assistant and the internet, 
intercepting requests in real time to detect and block sensitive data leaks before 
they leave your machine.

Built with mitmproxy and a local LLM (Ollama), it requires no cloud services and 
adds zero latency to allowed requests.

(docs/architecture.png)

---

## How it works

Every request VS Code sends to GitHub Copilot is intercepted by the proxy. The 
payload is parsed to extract the actual user query, then checked in two phases:

1. **Regex scan** — instantly flags API keys, tokens, and credentials matching 
   known patterns (OpenAI keys, GitHub tokens, AWS access keys, generic secrets)
2. **LLM policy check** — a local Llama model evaluates the request against a 
   custom policy defined in `instructions.md`

Requests that pass both checks are forwarded to Copilot. Anything that fails 
returns a `403 Policy Violation` with the reason logged.

---

## Requirements

- macOS (tested) / Linux
- Python 3.9+
- [mitmproxy](https://mitmproxy.org/)
- [Ollama](https://ollama.com/) with `llama3.2:1b` pulled

---

## Setup

**1. Install dependencies**

```bash
brew install --cask mitmproxy
pip install mitmproxy requests
ollama pull llama3.2:1b
```

**2. Trust the mitmproxy certificate**

Start mitmproxy once to generate the certificate, then trust it:

```bash
mitmproxy  # run briefly, then quit with q
sudo security add-trusted-cert -d -p ssl -p basic \
  -k /Library/Keychains/System.keychain \
  ~/.mitmproxy/mitmproxy-ca-cert.pem
```

**3. Configure VS Code**

Add to your `settings.json`:

```json
{
  "http.proxy": "http://127.0.0.1:8080",
  "http.proxySupport": "override",
  "http.proxyStrictSSL": false,
  "http.systemCertificates": true
}
```

**4. Define your policy**

Edit `instructions.md` to set what the LLM should block. Example: Do not allow sharing of internal project names, credentials, or any personally identifiable information.


---

## Running

Open two terminals:

```bash
# Terminal 1 — start the local LLM
ollama serve

# Terminal 2 — start the proxy
python3 start_gatekeeper.py
```

The proxy listens on `http://127.0.0.1:8080`. All Copilot requests from VS Code 
will now be intercepted and checked automatically.

---

## Test mode

Set `TEST_MODE=true` (default) to intercept all matched requests and return a 
mock response instead of forwarding to Copilot. Useful for testing your policy 
rules without consuming API quota.

```bash
TEST_MODE=true python3 start_gatekeeper.py   # no real requests sent
TEST_MODE=false python3 start_gatekeeper.py  # live mode
```

---

## Project structure

ai-gatekeeper/
├── gatekeeper.py        # core proxy logic — request parsing, regex, LLM check
├── start_gatekeeper.py  # launcher — starts mitmdump with gatekeeper.py
├── instructions.md      # your policy file — edit this to customise rules
├── requirements.txt
└── docs/
    └── architecture.png


---

## Verifying interception (optional)

To confirm the proxy is intercepting traffic before enabling the security layer:

```bash
./launch-with-mitmproxy.sh code .
```

This opens VS Code with mitmproxy running in a separate terminal so you can 
inspect raw traffic.

To manually test a proxied request:

```bash
curl --proxy http://127.0.0.1:8080 "http://wttr.in/?0"
```