import mcp
import sys

print("\n=== dir(mcp) ===")
print(dir(mcp))

for submodule in ['fastapi', 'web', 'main', 'app', 'server']:
    try:
        mod = __import__(f"mcp.{submodule}", fromlist=["*"])
        print(f"\n=== dir(mcp.{submodule}) ===")
        print(dir(mod))
    except ImportError as e:
        print(f"\n[!] Could not import mcp.{submodule}: {e}")

print("\n✅ MCP diagnostics complete.")
sys.exit(0)
