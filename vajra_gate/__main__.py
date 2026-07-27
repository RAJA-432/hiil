
import uvicorn

from vajra_gate.config import VAJRA_GATE_PORT

if __name__ == "__main__":
    uvicorn.run(
        "vajra_gate:app",
        host="127.0.0.1",
        port=VAJRA_GATE_PORT,
        reload=False,
        log_level="info",
        access_log=True,
    )
