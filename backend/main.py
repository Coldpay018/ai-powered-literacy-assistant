from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import Base, engine
import models


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def read_root():
    return {"message": "Literacy Learning Assistant backend is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
