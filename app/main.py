from fastapi import FastAPI

app = FastAPI(title="myapp")


@app.get("/")
def root():
    return {"message": "Hello World"}
