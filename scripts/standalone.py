from fastapi import FastAPI


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Kash AI is running!", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
