"""参考库路由。"""

from fastapi import APIRouter

from ..deps import get_engine
from ..models import ReferenceImportRequest, ReferenceSearchRequest
from ...reference.indexer import ReferenceIndexer

router = APIRouter(prefix="/api/v1", tags=["参考"])


@router.post("/references/import")
def reference_import(req: ReferenceImportRequest):
    engine = get_engine()
    store_path = engine.config.get("reference.store_path")
    indexer = ReferenceIndexer(store_path=store_path)
    novel = indexer.index_novel(file_path=req.file_path, title=req.title)
    return {"novel_id": novel.id, "title": novel.title, "chunk_count": novel.chunk_count}


@router.post("/references/search")
def reference_search(req: ReferenceSearchRequest):
    engine = get_engine()
    store_path = engine.config.get("reference.store_path")
    indexer = ReferenceIndexer(store_path=store_path)
    return {"results": indexer.search(query=req.query, top_k=req.top_k,
                                       source_filter=req.source_filter)}
