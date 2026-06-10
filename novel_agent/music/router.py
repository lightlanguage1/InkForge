"""音乐 API 路由 — 搜索 / 流媒体 / 收藏。"""

import logging
import random

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
import httpx

from .sources import (
    search_netease,
    get_stream_url_netease,
    get_stream_url_kugou,
    search_fallback,
    HEADERS_NE,
)
from .db import MusicDB
from ..user.context import get_current_user

router = APIRouter(prefix="/api/v1/music", tags=["音乐"])
logger = logging.getLogger(__name__)

# 懒加载单例
_music_db: MusicDB | None = None


def _db() -> MusicDB:
    global _music_db
    if _music_db is None:
        _music_db = MusicDB()
    return _music_db


def _uid() -> str:
    """获取当前登录用户 ID。"""
    return get_current_user()


# ═══════════════════════════════════════════
# 搜索
# ═══════════════════════════════════════════

@router.get("/search")
async def search(
    q: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, le=10),
    limit: int = Query(20, ge=5, le=50),
):
    """搜索歌曲 — 网易云音乐。"""
    try:
        results = await search_netease(q, page, limit)
        # 标记收藏状态
        user_id = _uid()
        fav_ids = _db().get_favorite_ids(user_id) if user_id else set()
        for r in results:
            r["favorited"] = r["id"] in fav_ids
        return {"results": results, "total": len(results)}
    except Exception as e:
        logger.warning("搜索失败: %s", e)
        return {"results": [], "total": 0}


# ═══════════════════════════════════════════
# 流媒体代理
# ═══════════════════════════════════════════

async def _proxy_stream(client: httpx.AsyncClient, cdn_url: str, request: Request):
    """从 CDN 代理流媒体数据到客户端。"""
    range_header = request.headers.get("range", "")
    cdn_headers = {"user-agent": HEADERS_NE["user-agent"], "accept": "*/*"}
    if range_header:
        cdn_headers["range"] = range_header

    cdn_resp = await client.get(cdn_url, headers=cdn_headers)
    if cdn_resp.status_code >= 400:
        raise HTTPException(status_code=502, detail="CDN 请求失败")

    content_type = cdn_resp.headers.get("content-type", "audio/mpeg")
    resp_headers = {
        "accept-ranges": "bytes",
        "cache-control": "public, max-age=3600",
    }
    if cdn_resp.headers.get("content-length"):
        resp_headers["content-length"] = cdn_resp.headers["content-length"]
    if cdn_resp.headers.get("content-range"):
        resp_headers["content-range"] = cdn_resp.headers["content-range"]
    if cdn_resp.status_code == 206:
        resp_headers["content-type"] = content_type

    return StreamingResponse(
        cdn_resp.aiter_bytes(chunk_size=65536),
        status_code=cdn_resp.status_code,
        media_type=content_type,
        headers=resp_headers,
    )


@router.get("/stream/{mid}")
async def stream(
    mid: str,
    request: Request,
    title: str = Query("", description="歌名（回退搜索用）"),
    artist: str = Query("", description="歌手（回退搜索用）"),
):
    """代理音频流 — 网易云为主，酷狗回退，歌名搜索兜底。"""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            # 1. 网易云
            cdn_url = await get_stream_url_netease(mid)
            if cdn_url:
                return await _proxy_stream(client, cdn_url, request)

            # 2. 酷狗（mid 可能是酷狗 hash）
            cdn_url = await get_stream_url_kugou(mid)
            if cdn_url:
                return await _proxy_stream(client, cdn_url, request)

            # 3. 回退搜索
            if title:
                cdn_url = await search_fallback(title, artist)
                if cdn_url:
                    return await _proxy_stream(client, cdn_url, request)

            raise HTTPException(status_code=404, detail="该歌曲暂无免费播放链接")

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("流媒体失败: %s", e)
        raise HTTPException(status_code=500, detail="获取播放链接失败")


# ═══════════════════════════════════════════
# 随机推荐（真·随机）
# ═══════════════════════════════════════════

# 高频中文单字 + 词组，覆盖全音乐频谱
_RANDOM_CHARS = list(
    "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严龙飞"
)

_RANDOM_PHRASES = [
    "爱", "心", "花", "风", "雨", "梦", "星", "夜", "光", "火", "雪", "海", "山", "云", "月",
    "春", "夏", "秋", "冬", "红", "蓝", "白", "黑", "金", "银", "笑", "泪", "路", "家", "暖",
    "远方", "旅行", "思念", "自由", "青春", "回忆", "时光", "承诺", "勇敢", "温柔",
    "lonely", "love", "dream", "fire", "rain", "dance", "star", "night", "heart",
    "piano", "guitar", "rock", "jazz", "blues", "soul", "folk", "pop",
]


@router.get("/random")
async def random_songs(
    limit: int = Query(20, ge=5, le=50),
):
    """随机推荐歌曲 — 真·随机中文单字或词组搜索。"""
    # 70% 概率用单字，30% 用词组，确保每次搜索结果不同
    if random.random() < 0.7:
        keyword = random.choice(_RANDOM_CHARS)
    else:
        keyword = random.choice(_RANDOM_PHRASES)

    try:
        results = await search_netease(keyword, 1, limit * 2)
        random.shuffle(results)
        results = results[:limit]
        user_id = _uid()
        fav_ids = _db().get_favorite_ids(user_id) if user_id else set()
        for r in results:
            r["favorited"] = r["id"] in fav_ids
        return {"results": results, "total": len(results)}
    except Exception as e:
        logger.warning("随机推荐失败: %s", e)
        return {"results": [], "total": 0}


# ═══════════════════════════════════════════
# 收藏
# ═══════════════════════════════════════════

@router.get("/favorites")
async def list_favorites():
    """获取收藏列表。"""
    try:
        return {"results": _db().get_favorites(_uid()), "total": 0}
    except Exception as e:
        logger.warning("获取收藏失败: %s", e)
        return {"results": [], "total": 0}


@router.post("/favorites")
async def add_favorite(request: Request):
    """收藏歌曲。body: {id, mid, title, artist, album?, duration?, artwork?}"""
    try:
        body = await request.json()
        inserted = _db().add_favorite(_uid(), body)
        return {"ok": True, "inserted": inserted}
    except Exception as e:
        logger.warning("收藏失败: %s", e)
        raise HTTPException(status_code=500, detail="收藏失败")


@router.delete("/favorites/{song_id}")
async def remove_favorite(song_id: str):
    """取消收藏。"""
    try:
        removed = _db().remove_favorite(_uid(), song_id)
        return {"ok": True, "removed": removed}
    except Exception as e:
        logger.warning("取消收藏失败: %s", e)
        raise HTTPException(status_code=500, detail="取消收藏失败")


@router.get("/favorites/ids")
async def favorite_ids():
    """获取收藏的 song_id 集合（用于前端快速判断）。"""
    try:
        return {"ids": list(_db().get_favorite_ids(_uid()))}
    except Exception as e:
        logger.warning("获取收藏ID失败: %s", e)
        return {"ids": []}
