import subprocess
import os
import signal
import sys

def run_service():
    # Ensure the script path is absolute to avoid issues when running from different dirs
    base_path = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(base_path, "gatekeeper.py")
    
    # 1. Check if gatekeeper.py actually exists
    if not os.path.exists(script_path):
        print(f"❌ Error: {script_path} not found!")
        sys.exit(1)

    print("🛡️  Gatekeeper Firewall is ACTIVE")
    print("📍 Proxy Address: http://127.0.0.1:8080")
    print("📝 Logic Script:  gatekeeper.py")
    print("🛑 Press Ctrl+C to stop the firewall")
    
    # --quiet: Keeps the terminal clean so you only see your [BLOCKED] prints
    # --set block_global=false: Useful if you're testing on a local network
    cmd = ["mitmdump", "-p", "8080", "-s", script_path, "--quiet"]
    
    try:
        # Using subprocess.Popen allows for cleaner exit handling
        process = subprocess.Popen(cmd)
        process.wait()
    except KeyboardInterrupt:
        print("\n\n🛡️  Shutting down Gatekeeper safely...")
        process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    run_service()