"""System status and dashboard stats."""
import platform
import shutil

from fastapi import APIRouter

from backend.config import settings
from backend.services import chat as chat_service
from backend.services import registry, vectorstore

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/stats")
def stats():
    reg = registry.stats()
    try:
        chunk_total = vectorstore.count()
    except Exception:
        chunk_total = reg.get("chunks", 0)
    return {
        "documents": reg["documents"],
        "chunks": chunk_total,
        "properties": reg["properties"],
        "chat_model": settings.chat_model,
        "embed_model": settings.embed_model,
        "vector_db": "ChromaDB (local)",
    }


@router.get("/system")
def system():
    info: dict = {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "cpu": platform.processor() or platform.machine(),
    }
    try:
        import psutil

        vm = psutil.virtual_memory()
        info["cpu_count"] = psutil.cpu_count(logical=True)
        info["ram_total_gb"] = round(vm.total / 1e9, 1)
        info["ram_used_percent"] = vm.percent
    except Exception:
        info["ram_total_gb"] = None

    try:
        usage = shutil.disk_usage(str(settings.data_dir))
        info["disk_total_gb"] = round(usage.total / 1e9, 1)
        info["disk_free_gb"] = round(usage.free / 1e9, 1)
    except Exception:
        pass

    info["models"] = chat_service.health()
    info["vector_db"] = "ChromaDB (local, embedded)"
    info["data_dir"] = str(settings.data_dir)
    return info
