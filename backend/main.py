from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import auth, sessions, intervention, websocket, jobs, training, proposals

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PENTAGON API",
    description="AI-Powered Image Semantic Segmentation Training Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(jobs.router)
app.include_router(training.router)
app.include_router(proposals.router)
app.include_router(intervention.router)
app.include_router(websocket.router)


@app.get("/")
def root():
    return {"message": "PENTAGON API is running"}