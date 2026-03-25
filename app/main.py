from fastapi import FastAPI

app = FastAPI(title="myapp")


@app.get("/")
def root():
    return {"message": "Hello World - updated"}


@app.get("/version")
def version():
    return {"version": "1.1.0", "status": "updated"}
