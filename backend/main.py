from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import auth, sessions, intervention, websocket

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PENTAGON API",
    description="AI-Powered Image Semantic Segmentation Training Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://pentagon-frontend-six.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(sessions.router)
app.include_router(intervention.router)
app.include_router(websocket.router)


@app.get("/")
def root():
    return {"message": "PENTAGON API is running"}