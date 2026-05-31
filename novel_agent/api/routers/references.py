"""参考库路由。"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

from ..deps import get_engine
from ..models import ReferenceImportRequest, ReferenceSearchRequest
from ...reference.indexer import ReferenceIndexer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["参考"])


@router.post("/references/import")
def reference_import(req: ReferenceImportRequest):
    engine = get_engine()
    store_path = engine.config.get("reference.store_path")
    indexer = ReferenceIndexer(store_path=store_path)
    novel = indexer.index_novel(file_path=req.file_path, title=req.title)
    return {"novel_id": novel.id, "title": novel.title, "chunk_count": novel.chunk_count}


@router.post("/references/import/upload")
def reference_upload(file: UploadFile = File(...)):
    """Upload reference novel via browser drag-and-drop."""
    tmp = Path(tempfile.gettempdir()) / f"inkforge_ref_{file.filename}"
    tmp.write_bytes(file.file.read())
    try:
        engine = get_engine()
        store_path = engine.config.get("reference.store_path")
        indexer = ReferenceIndexer(store_path=store_path)
        title = file.filename.rsplit(".", 1)[0]
        novel = indexer.index_novel(file_path=str(tmp), title=title)
    except Exception:
        logger.exception("参考导入失败: %s", file.filename)
        raise HTTPException(status_code=500, detail="参考导入失败")
    finally:
        try: tmp.unlink()
        except OSError: pass
    return {"novel_id": novel.id, "title": novel.title, "chunk_count": novel.chunk_count}


@router.post("/references/search")
def reference_search(req: ReferenceSearchRequest):
    engine = get_engine()
    store_path = engine.config.get("reference.store_path")
    indexer = ReferenceIndexer(store_path=store_path)
    return {"results": indexer.search(query=req.query, top_k=req.top_k,
                                       source_filter=req.source_filter)}
