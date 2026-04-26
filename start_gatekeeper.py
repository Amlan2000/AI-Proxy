import cmd
import subprocess
import os
import signal
import sys

def run_service():
    base_path = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(base_path, "gatekeeper.py")
    
    if not os.path.exists(script_path):
        print(f"❌ Error: {script_path} not found!")
        sys.exit(1)

    print("🛡️  Gatekeeper Firewall is ACTIVE")
    print("📍 Proxy Address: http://127.0.0.1:8080")
    print("📝 Logic Script:  gatekeeper.py")
    print("🛑 Press Ctrl+C to stop the firewall")
    
    cmd = ["mitmdump", "-p", "8080", "-s", script_path, "--quiet"]
    
    try:
        env = os.environ.copy()
        env["TEST_MODE"] = "true"   # flip to "false" for production
        process = subprocess.Popen(cmd, env=env)
        process.wait()
    except KeyboardInterrupt:
        print("\n\n🛡️  Shutting down Gatekeeper safely...")
        process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    run_service()