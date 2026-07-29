
import uvicorn

from vajra_gate.config import VAJRA_GATE_PORT


def run_gateway() -> None:
    uvicorn.run(
        "vajra_gate:app",
        host="127.0.0.1",
        port=VAJRA_GATE_PORT,
        reload=False,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    run_gateway()
