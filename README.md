# AI-Proxy

brew install --cask mitmproxy


sudo security add-trusted-cert -d -p ssl -p basic -k /Library/Keychains/System.keychain ~/.mitmproxy/mitmproxy-ca-cert.pem


Just observing traffic

Terminal -1 : mitmproxy
Terminal -2: curl --proxy http://127.0.0.1:8080 "http://wttr.in/Dunedin?0" 


Intercepting requests

1. Mitmproxy -> press ‘i’ -> set intercept ‘i:~u /Dunedin & ~q’
2. curl --proxy http://127.0.0.1:8080 "http://wttr.in/Dunedin?0" -> you will see request in red getting intercepted
3. Press ‘a’ to resume the request


3.settings.json

{
 "python.defaultInterpreterPath": "/usr/local/bin/python3",
 "python.createEnvironment.trigger": "off",
 "python.analysis.autoImportCompletions": true,
 "github.copilot.enable": {
   "*": true,
   "plaintext": false,
   "markdown": false,
   "scminput": false,
   "python": true
 },
 "terminal.integrated.initialHint": false,
 "chat.viewSessions.orientation": "stacked",
 "git.autofetch": true,
 "http.systemCertificates": true,
 "http.fetchAdditionalSupport": true,
 "http.proxy": "http://127.0.0.1:8080",
 "http.proxySupport": "override",
 "http.proxyStrictSSL": false,
}


4. You can also just run './launch-with-mitmproxy.sh code .' . This will open mitmproxy in another terminal

5. Start the gatekeeper file using something like " python3 start_gatekeeper.py" in one terminal and 
   Run local ollama in another terminal using 'ollama serve' 
