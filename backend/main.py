from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from routers.detect import router as detect_router
from routers.system import router as system_router
from routers.garak_scan import router as garak_router
from routers.kb import router as kb_router
from routers.guardrail import router as guardrail_router
import config

app = FastAPI(title="AIGC 内容安全审核系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(detect_router)
app.include_router(system_router)
app.include_router(garak_router)
app.include_router(kb_router)
app.include_router(guardrail_router)

from fastapi.responses import FileResponse


@app.get("/api/health", tags=["system"])
async def health_check():
    return {"status": "ok", "service": "aigc-safety-system"}

dist = Path(__file__).parent.parent / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = dist / "index.html"
        return FileResponse(str(index))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)
