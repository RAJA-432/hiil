import asyncio
import os
import sys

import httpx

# Configuration - matches my_streamlit_app.py
# Override via the HIIL_API_BASE env var, e.g. HIIL_API_BASE=http://localhost:9000.
API_BASE = os.environ.get("HIIL_API_BASE", "http://127.0.0.1:8000")
ENDPOINTS_TO_TEST = [
    "/api/status",
    "/api/models",
    "/api/usage",
    "/api/sessions",
]

class AppValidator:
    def __init__(self):
        self.results = {
            "backend_api": [],
            "connectivity": False,
            "response_headers": [],
            "errors": []
        }

    def log_result(self, test_name: str, success: bool, detail: str = ""):
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"[{status}] {test_name} {detail}")
        return success

    async def check_connectivity(self):
        print("\n--- 📡 Checking Connectivity ---")
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{API_BASE}/api/status")
                if resp.status_code == 200:
                    self.results["connectivity"] = True
                    return self.log_result("Backend Reachability", True, "API is online")
                else:
                    self.results["connectivity"] = False
                    return self.log_result("Backend Reachability", False, f"Status code: {resp.status_code}")
        except Exception as e:
            self.results["connectivity"] = False
            return self.log_result("Backend Reachability", False, str(e))

    async def check_content_length_issue(self):
        print("\n--- 📏 Checking Content-Length Integrity ---")
        success_all = True
        async with httpx.AsyncClient(timeout=5.0) as client:
            for ep in ENDPOINTS_TO_TEST:
                try:
                    resp = await client.get(f"{API_BASE}{ep}")
                    content_length = resp.headers.get("Content-Length")
                    actual_length = len(resp.content)

                    if content_length:
                        cl_val = int(content_length)
                        self.results["response_headers"].append({ep: content_length})
                        if cl_val != actual_length:
                            self.log_result(f"Header Match {ep}", False,
                                           f"Expected {cl_val} bytes, got {actual_length}")
                            self.results["errors"].append(
                                f"{ep}: Content-Length {cl_val} != actual {actual_length} bytes"
                            )
                            success_all = False
                        else:
                            self.log_result(f"Header Match {ep}", True)
                    else:
                        self.results["response_headers"].append({ep: None})
                        self.log_result(f"Header Match {ep}", True, "No manual Content-Length header (Good)")
                except Exception as e:
                    self.log_result(f"Request {ep}", False, str(e))
                    self.results["errors"].append(f"{ep}: {e}")
                    success_all = False
        return success_all

    async def validate_all(self):
        print("🚀 Starting hiil Application Health Audit...")
        print(f"Target API: {API_BASE}")

        connected = await self.check_connectivity()
        if not connected:
            print("\n🚨 CRITICAL: Backend is unreachable. Please start the API server first.")
            return self.results

        header_ok = await self.check_content_length_issue()

        print("\n--- 🏁 Final Report ---")
        print(f"Connectivity: {'🟢 OK' if connected else '🔴 FAIL'}")
        print(f"Response Integrity: {'🟢 OK' if header_ok else '🔴 FAIL (Content-Length mismatch found)'}")
        if self.results["errors"]:
            print(f"Errors: {self.results['errors']}")

        if not header_ok:
            print("\n💡 Recommendation: Remove manual Content-Length headers in the FastAPI responses.")

        return self.results

async def main():
    validator = AppValidator()
    await validator.validate_all()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Validator crashed: {e}")
        sys.exit(1)
