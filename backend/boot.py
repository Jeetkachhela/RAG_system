import traceback
import uvicorn

try:
    uvicorn.run("main:app", host="0.0.0.0", port=8001)
except BaseException as e:
    with open("crash.log", "w") as f:
        f.write(traceback.format_exc())
