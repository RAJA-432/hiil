import os

import uvicorn

from vajram.config import VAJRAM_PORT

if __name__ == "__main__":
    uvicorn.run("vajram:app", host="0.0.0.0", port=VAJRAM_PORT, reload=False)
