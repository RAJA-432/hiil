
import uvicorn

from vajram.config import VAJRAM_PORT

if __name__ == "__main__":
    uvicorn.run("vajram:app", host="127.0.0.1", port=VAJRAM_PORT, reload=False)
