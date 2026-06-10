"""音乐源 API 封装 — 网易云（主）+ 酷狗（回退）。"""

import logging
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

HEADERS_NE = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "referer": "https://music.163.com",
}

HEADERS_KG = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "referer": "https://m.kugou.com",
}


async def search_netease(q: str, page: int = 1, limit: int = 20) -> List[Dict[str, Any]]:
    """搜索网易云音乐。"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "http://music.163.com/api/search/get",
            data={"s": q, "type": 1, "limit": limit, "offset": (page - 1) * limit},
            headers=HEADERS_NE,
        )
        data = resp.json()
        songs = data.get("result", {}).get("songs", [])

        results = []
        for s in songs:
            sid = str(s.get("id", ""))
            artists = ", ".join(a.get("name", "") for a in s.get("artists", []) if a.get("name"))
            album = s.get("album", {})
            artwork = album.get("picUrl", "") or album.get("blurPicUrl", "")
            results.append({
                "id": sid,
                "mid": sid,
                "title": s.get("name", ""),
                "artist": artists,
                "album": album.get("name", ""),
                "duration": s.get("duration", 0) // 1000,
                "artwork": artwork,
            })
        return results


async def get_stream_url_netease(song_id: str) -> Optional[str]:
    """获取网易云歌曲 CDN 流链接，失败返回 None。"""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            resp = await client.get(
                f"http://music.163.com/song/media/outer/url?id={song_id}.mp3",
                headers=HEADERS_NE,
            )
            if resp.status_code == 302:
                location = resp.headers.get("location", "")
                if location and "/404" not in location and location.startswith("http"):
                    return location
    except Exception as e:
        logger.debug("netease stream failed: %s", e)
    return None


async def get_stream_url_kugou(hash_val: str) -> Optional[str]:
    """获取酷狗歌曲 CDN 流链接，失败返回 None。"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "http://m.kugou.com/app/i/getSongInfo.php",
                params={"cmd": "playInfo", "hash": hash_val},
                headers=HEADERS_KG,
            )
            data = resp.json()
            if data.get("errcode") == 0 and data.get("url"):
                return data["url"]
    except Exception as e:
        logger.debug("kugou stream failed: %s", e)
    return None


async def search_fallback(title: str, artist: str) -> Optional[str]:
    """用歌名+歌手尝试找可播放的流链接（先网易云，再酷狗）。"""
    search_q = f"{title} {artist}".strip()
    logger.info("回退搜索: %s", search_q)

    # 1. 网易云备选
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "http://music.163.com/api/search/get",
                data={"s": search_q, "type": 1, "limit": 10, "offset": 0},
                headers=HEADERS_NE,
            )
            songs = resp.json().get("result", {}).get("songs", [])
            for s in songs:
                sid = str(s.get("id", ""))
                if not sid:
                    continue
                url = await get_stream_url_netease(sid)
                if url:
                    logger.info("网易云备选命中: id=%s title=%s", sid, s.get("name", ""))
                    return url
    except Exception as e:
        logger.debug("netease fallback failed: %s", e)

    # 2. 酷狗备选（检查 hash/320hash/sqhash）
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "http://mobilecdn.kugou.com/api/v3/search/song",
                params={"format": "json", "keyword": search_q, "page": 1, "pagesize": 20},
                headers=HEADERS_KG,
            )
            candidates = resp.json().get("data", {}).get("info", [])
            for c in candidates:
                for key in ("hash", "320hash", "sqhash"):
                    h = c.get(key, "")
                    if not h:
                        continue
                    url = await get_stream_url_kugou(h)
                    if url:
                        logger.info("酷狗备选命中: hash=%s key=%s title=%s", h[:12], key, c.get("songname", ""))
                        return url
    except Exception as e:
        logger.debug("kugou fallback failed: %s", e)

    return None
