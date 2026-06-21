"""Vector store for semantic search using ChromaDB."""

import functools
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

from .entities import Character, Location, Scene, Lore, Faction, OpenLoop

logger = logging.getLogger(__name__)


def _repair_sqlite_wal(index_path: Path):
    """修复 SQLite WAL 锁死 / DBMOVED——删除 WAL/SHM + 强制 checkpoint 恢复。

    容器重启后 Volume inode 变化导致 SQLITE_READONLY_DBMOVED (code 1032)。
    ChromaDB 的 PersistentClient 没有 close() 方法，del 不释放底层连接。
    解决方案：用 sqlite3 直接 checkpoint 所有数据库，然后删 WAL/SHM 重建连接。
    """
    import sqlite3 as _sqlite3
    repaired = 0
    # 先对每个 sqlite3 文件做 WAL checkpoint（核心：解决 DBMOVED）
    for db_file in index_path.rglob("*.sqlite3"):
        try:
            conn = _sqlite3.connect(str(db_file))
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
            repaired += 1
        except Exception:
            pass
    # 再删 WAL/SHM 残留
    for suffix in ("-wal", "-shm"):
        for f in index_path.rglob(f"*.sqlite3{suffix}"):
            try:
                os.remove(str(f))
            except OSError:
                pass
    if repaired:
        logger.warning("已修复 %d 个 SQLite 数据库（WAL checkpoint）", repaired)


def _retry_on_readonly(method):
    """装饰器：捕获 SQLite readonly (1032) 错误，自动修复并重试一次。"""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            if _is_readonly_error(e):
                logger.warning("SQLite readonly 检测到，尝试修复后重试 %s", method.__name__)
                self._repair_and_reconnect()
                return method(self, *args, **kwargs)
            raise
    return wrapper


def _is_readonly_error(exc: Exception) -> bool:
    """检测是否为 SQLite readonly (1032) 错误。"""
    msg = str(exc)
    if "1032" in msg and "readonly" in msg.lower():
        return True
    if "readonly database" in msg.lower():
        return True
    if "SQLITE_READONLY" in msg:
        return True
    return False


class VectorStore:
    """Manages semantic search using ChromaDB. 实例按 project_path 缓存——避免重复创建
    PersistentClient 导致 SQLITE_READONLY_DBMOVED。"""

    _instances: dict[str, "VectorStore"] = {}

    def __new__(cls, project_path: Path):
        key = str(Path(project_path).resolve())
        if key in cls._instances:
            return cls._instances[key]
        instance = super().__new__(cls)
        cls._instances[key] = instance
        return instance

    def __init__(self, project_path: Path):
        # 避免重复初始化（__new__ 返回缓存实例后 __init__ 仍会调用）
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.project_path = Path(project_path)
        self.index_path = self.project_path / "memory" / "index"
        self.index_path.mkdir(parents=True, exist_ok=True)

        # 启动自愈：修复上次异常关闭导致的 WAL 锁死
        _repair_sqlite_wal(self.index_path)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.index_path),
            settings=Settings(anonymized_telemetry=False, chroma_sqlite_timeout=60000)
        )

        # Initialize collections with readonly retry
        self._init_collections()

    def _init_collections(self):
        """创建或获取所有 collection。readonly 时自动修复重试。"""
        try:
            self.characters_collection = self.client.get_or_create_collection(
                name="characters",
                metadata={"description": "Character entities"}
            )
            self.locations_collection = self.client.get_or_create_collection(
                name="locations",
                metadata={"description": "Location entities"}
            )
            self.scenes_collection = self.client.get_or_create_collection(
                name="scenes",
                metadata={"description": "Scene summaries"}
            )
            self.lore_collection = self.client.get_or_create_collection(
                name="lore",
                metadata={"description": "World rules and lore (Phase 7A.4)"}
            )
            self.factions_collection = self.client.get_or_create_collection(
                name="factions",
                metadata={"description": "Faction/organization entities"}
            )
            self.loops_collection = self.client.get_or_create_collection(
                name="loops",
                metadata={"description": "Open loop / story thread entities"}
            )
        except Exception as e:
            if _is_readonly_error(e):
                logger.warning("ChromaDB init 遇到 readonly，尝试修复后重试")
                self._repair_and_reconnect()
                # 修复后再次尝试
                self.characters_collection = self.client.get_or_create_collection(
                    name="characters",
                    metadata={"description": "Character entities"}
                )
                self.locations_collection = self.client.get_or_create_collection(
                    name="locations",
                    metadata={"description": "Location entities"}
                )
                self.scenes_collection = self.client.get_or_create_collection(
                    name="scenes",
                    metadata={"description": "Scene summaries"}
                )
                self.lore_collection = self.client.get_or_create_collection(
                    name="lore",
                    metadata={"description": "World rules and lore (Phase 7A.4)"}
                )
                self.factions_collection = self.client.get_or_create_collection(
                    name="factions",
                    metadata={"description": "Faction/organization entities"}
                )
                self.loops_collection = self.client.get_or_create_collection(
                    name="loops",
                    metadata={"description": "Open loop / story thread entities"}
                )
            else:
                raise

    def _repair_and_reconnect(self):
        """运行时自愈：清理 WAL 残留并重建 ChromaDB 客户端连接。

        容器重启 / Volume inode 变化后 SQLite 会进入 readonly 状态。
        此方法删除 WAL/SHM、重建客户端和所有 collection 引用。
        """
        # 先关闭旧客户端
        try:
            del self.client
        except Exception:
            pass

        # 清理 WAL/SHM
        _repair_sqlite_wal(self.index_path)

        # 重建客户端
        self.client = chromadb.PersistentClient(
            path=str(self.index_path),
            settings=Settings(anonymized_telemetry=False, chroma_sqlite_timeout=60000)
        )

        # 重新获取所有 collection
        self.characters_collection = self.client.get_or_create_collection(
            name="characters",
            metadata={"description": "Character entities"}
        )
        self.locations_collection = self.client.get_or_create_collection(
            name="locations",
            metadata={"description": "Location entities"}
        )
        self.scenes_collection = self.client.get_or_create_collection(
            name="scenes",
            metadata={"description": "Scene summaries"}
        )
        self.lore_collection = self.client.get_or_create_collection(
            name="lore",
            metadata={"description": "World rules and lore (Phase 7A.4)"}
        )
        self.factions_collection = self.client.get_or_create_collection(
            name="factions",
            metadata={"description": "Faction/organization entities"}
        )
        self.loops_collection = self.client.get_or_create_collection(
            name="loops",
            metadata={"description": "Open loop / story thread entities"}
        )
        logger.info("ChromaDB 客户端已重建（SQLite readonly 自愈）")
    
    # ========================================================================
    # Indexing Methods
    # ========================================================================

    @_retry_on_readonly
    def index_character(self, character: Character):
        """Add or update character in vector index.
        
        Args:
            character: Character entity to index
        """
        # Build searchable text from character attributes
        text_parts = [
            f"Name: {character.full_name}",
            f"First name: {character.first_name}",
            f"Family name: {character.family_name}" if character.family_name else "",
            f"Title: {character.title}" if character.title else "",
            f"Nicknames: {', '.join(character.nicknames)}" if character.nicknames else "",
            f"Role: {character.role}",
            f"Description: {character.description}",
            f"Traits: {', '.join(character.personality.core_traits)}" if character.personality.core_traits else "",
            f"Fears: {', '.join(character.personality.fears)}" if character.personality.fears else "",
            f"Desires: {', '.join(character.personality.desires)}" if character.personality.desires else "",
            f"Backstory: {character.backstory}",
            f"Goals: {', '.join(character.current_state.goals)}" if character.current_state.goals else "",
        ]
        
        text = " ".join([part for part in text_parts if part])
        
        # Metadata for filtering
        metadata = {
            "entity_type": "character",
            "name": character.full_name,
            "first_name": character.first_name,
            "role": character.role,
            "updated_at": character.updated_at
        }
        
        # Upsert to collection
        self.characters_collection.upsert(
            ids=[character.id],
            documents=[text],
            metadatas=[metadata]
        )
    
    @_retry_on_readonly
    def index_location(self, location: Location):
        """Add or update location in vector index.
        
        Args:
            location: Location entity to index
        """
        # Build searchable text
        text_parts = [
            f"Name: {location.name}",
            f"Aliases: {', '.join(location.aliases)}" if location.aliases else "",
            f"Description: {location.description}",
            f"Atmosphere: {location.atmosphere}",
            f"Visual: {location.sensory_details.visual}" if location.sensory_details.visual else "",
            f"Auditory: {location.sensory_details.auditory}" if location.sensory_details.auditory else "",
            f"Olfactory: {location.sensory_details.olfactory}" if location.sensory_details.olfactory else "",
            f"Features: {', '.join(location.features)}" if location.features else "",
            f"Significance: {location.significance}",
        ]
        
        text = " ".join([part for part in text_parts if part])
        
        metadata = {
            "entity_type": "location",
            "name": location.name,
            "updated_at": location.updated_at
        }
        
        self.locations_collection.upsert(
            ids=[location.id],
            documents=[text],
            metadatas=[metadata]
        )
    
    @_retry_on_readonly
    def index_scene(self, scene: Scene):
        """Add or update scene in vector index.
        
        Args:
            scene: Scene entity to index
        """
        # Build searchable text from scene summary and events
        text_parts = [
            f"Title: {scene.title}",
            f"Summary: {' '.join(scene.summary)}" if scene.summary else "",
            f"Key Events: {', '.join(scene.key_events)}" if scene.key_events else "",
            f"Emotional Beats: {', '.join(scene.emotional_beats)}" if scene.emotional_beats else "",
        ]
        
        text = " ".join([part for part in text_parts if part])
        
        metadata = {
            "entity_type": "scene",
            "tick": scene.tick,
            "pov_character_id": scene.pov_character_id,
            "location_id": scene.location_id,
            "created_at": scene.created_at
        }
        
        self.scenes_collection.upsert(
            ids=[scene.id],
            documents=[text],
            metadatas=[metadata]
        )

    @_retry_on_readonly
    def index_faction(self, faction: Faction):
        """Add or update faction in vector index.
        
        Args:
            faction: Faction entity to index
        """
        text_parts = [
            f"Name: {faction.name}",
            f"Type: {faction.org_type}",
            f"Summary: {faction.summary}",
            f"Mandate: {', '.join(faction.mandate_objectives)}" if faction.mandate_objectives else "",
            f"Influence: {', '.join(faction.influence_domains)}" if faction.influence_domains else "",
            f"Assets: {', '.join(faction.assets_resources)}" if faction.assets_resources else "",
            f"Methods: {', '.join(faction.methods_tactics)}" if faction.methods_tactics else "",
            f"Tags: {', '.join(faction.tags)}" if faction.tags else "",
            f"Importance: {faction.importance}",
        ]
        text = " ".join([p for p in text_parts if p])
        metadata = {
            "entity_type": "faction",
            "name": faction.name,
            "org_type": faction.org_type,
            "importance": faction.importance,
            "tags": "|".join(faction.tags) if faction.tags else "",
            "updated_at": faction.updated_at,
        }
        self.factions_collection.upsert(
            ids=[faction.id],
            documents=[text],
            metadatas=[metadata]
        )
    
    @_retry_on_readonly
    def index_loop(self, loop: OpenLoop):
        """Add or update open loop in vector index.

        Args:
            loop: OpenLoop entity to index
        """
        # Build searchable text from loop fields
        parts = [loop.description]
        if hasattr(loop, 'category') and loop.category:
            parts.append(loop.category)
        if hasattr(loop, 'resolution_hint') and loop.resolution_hint:
            parts.append(loop.resolution_hint)
        text = " ".join(parts)

        metadata = {
            "entity_type": "loop",
            "id": loop.id,
            "priority": loop.priority if hasattr(loop, 'priority') else 0,
            "status": loop.status if hasattr(loop, 'status') else "open",
        }

        # Remove existing entry if present
        existing = self.loops_collection.get(ids=[loop.id])
        if existing and existing["ids"]:
            self.loops_collection.delete(ids=[loop.id])

        self.loops_collection.add(
            ids=[loop.id],
            documents=[text],
            metadatas=[metadata]
        )

    # ========================================================================
    # Search Methods
    # ========================================================================

    @_retry_on_readonly
    def search_characters(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant characters.
        
        Args:
            query: Natural language search query
            limit: Maximum number of results
        
        Returns:
            List of search results with id, distance, metadata, and document
        """
        results = self.characters_collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        return self._format_results(results)
    
    @_retry_on_readonly
    def search_locations(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant locations.
        
        Args:
            query: Natural language search query
            limit: Maximum number of results
        
        Returns:
            List of search results
        """
        results = self.locations_collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        return self._format_results(results)
    
    @_retry_on_readonly
    def search_scenes(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant scenes.
        
        Args:
            query: Natural language search query
            limit: Maximum number of results
        
        Returns:
            List of search results
        """
        results = self.scenes_collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        return self._format_results(results)
    
    @_retry_on_readonly
    def search(self, query: str, entity_types: Optional[List[str]] = None,
               limit: int = 5) -> List[Dict[str, Any]]:
        """Search across multiple entity types.
        
        Args:
            query: Natural language search query
            entity_types: List of entity types to search (character, location, scene)
                         If None, searches all types
            limit: Maximum number of results per type
        
        Returns:
            List of search results sorted by relevance
        """
        if entity_types is None:
            entity_types = ["character", "location", "scene", "faction", "loop"]

        # 动态匹配实体类型——能对上就用，对不上的搜全部
        # 不硬编码映射表，防止 LLM 输出新类型时被静默丢弃
        _KNOWN = {"character", "location", "scene", "faction", "loop"}
        resolved = set()
        unknown_found = False
        for t in entity_types:
            if t in _KNOWN:
                resolved.add(t)
                continue
            # 尝试子串匹配（如 "characters" 匹配 "character"）
            matched = False
            for k in _KNOWN:
                if k in t or t in k:
                    resolved.add(k)
                    matched = True
                    break
            if not matched:
                unknown_found = True
        if unknown_found:
            entity_types = list(_KNOWN)  # 全搜，不丢数据
        else:
            entity_types = list(resolved)

        all_results = []

        if "character" in entity_types:
            char_results = self.search_characters(query, limit)
            all_results.extend(char_results)

        if "location" in entity_types:
            loc_results = self.search_locations(query, limit)
            all_results.extend(loc_results)

        if "scene" in entity_types:
            scene_results = self.search_scenes(query, limit)
            all_results.extend(scene_results)
        if "faction" in entity_types:
            fac_results = self.search_factions(query, limit)
            all_results.extend(fac_results)
        if "loop" in entity_types:
            loop_results = self.search_loops(query, limit)
            all_results.extend(loop_results)
        
        # Sort by distance (lower is better)
        all_results.sort(key=lambda x: x["distance"])
        
        return all_results[:limit]

    @_retry_on_readonly
    def search_factions(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant factions.
        
        Args:
            query: Natural language search query
            limit: Maximum number of results
        
        Returns:
            List of search results
        """
        results = self.factions_collection.query(
            query_texts=[query],
            n_results=limit
        )
        return self._format_results(results)

    @_retry_on_readonly
    def search_loops(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant open loops.

        Args:
            query: Natural language search query
            limit: Maximum number of results

        Returns:
            List of search results
        """
        results = self.loops_collection.query(
            query_texts=[query],
            n_results=limit
        )
        return self._format_results(results)

    def _format_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format ChromaDB results into a consistent structure.
        
        Args:
            results: Raw results from ChromaDB query
        
        Returns:
            List of formatted result dictionaries
        """
        formatted = []
        
        # ChromaDB returns results in nested lists
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]
        
        for i in range(len(ids)):
            formatted.append({
                "entity_id": ids[i],
                "distance": distances[i],
                "relevance_score": 1.0 - min(distances[i], 1.0),  # Convert distance to 0-1 score
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "snippet": documents[i] if i < len(documents) else ""
            })
        
        return formatted
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    @_retry_on_readonly
    def delete_entity(self, entity_id: str):
        """Delete an entity from all collections.
        
        Args:
            entity_id: Entity ID to delete
        """
        # Try to delete from all collections (will silently fail if not present)
        try:
            self.characters_collection.delete(ids=[entity_id])
        except:
            pass
        
        try:
            self.locations_collection.delete(ids=[entity_id])
        except:
            pass
        
        try:
            self.scenes_collection.delete(ids=[entity_id])
        except:
            pass
    
    def get_collection_counts(self) -> Dict[str, int]:
        """Get count of entities in each collection.
        
        Returns:
            Dictionary with counts for each entity type
        """
        return {
            "characters": self.characters_collection.count(),
            "locations": self.locations_collection.count(),
            "scenes": self.scenes_collection.count(),
            "lore": self.lore_collection.count(),
            "factions": self.factions_collection.count(),
        }
    
    # ========================================================================
    # Lore Methods (Phase 7A.4)
    # ========================================================================
    
    @_retry_on_readonly
    def index_lore(self, lore: Lore):
        """Add or update lore in vector index (Phase 7A.4).
        
        Args:
            lore: Lore entity to index
        """
        # Build searchable text from lore attributes
        text_parts = [
            f"Type: {lore.lore_type}",
            f"Category: {lore.category}",
            f"Content: {lore.content}",
            f"Tags: {', '.join(lore.tags)}" if lore.tags else "",
            f"Importance: {lore.importance}"
        ]
        
        searchable_text = "\n".join([p for p in text_parts if p])
        
        # Prepare metadata
        metadata = {
            "type": "lore",
            "lore_type": lore.lore_type,
            "category": lore.category,
            "importance": lore.importance,
            "source_scene": lore.source_scene_id,
            "tick": lore.tick
        }
        
        # Upsert to collection
        self.lore_collection.upsert(
            ids=[lore.id],
            documents=[searchable_text],
            metadatas=[metadata]
        )
    
    @_retry_on_readonly
    def search_lore(
        self,
        query: str,
        n_results: int = 5,
        category: Optional[str] = None,
        lore_type: Optional[str] = None,
        importance: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant lore (Phase 7A.4).
        
        Args:
            query: Search query
            n_results: Number of results to return
            category: Optional category filter
            lore_type: Optional type filter
            importance: Optional importance filter
        
        Returns:
            List of lore search results with metadata
        """
        # Build where filter
        where = {}
        if category:
            where["category"] = category
        if lore_type:
            where["lore_type"] = lore_type
        if importance:
            where["importance"] = importance
        
        # Search
        results = self.lore_collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where if where else None
        )
        
        # Format results
        formatted_results = []
        if results and results['ids'] and results['ids'][0]:
            for i, lore_id in enumerate(results['ids'][0]):
                formatted_results.append({
                    "id": lore_id,
                    "distance": results['distances'][0][i] if 'distances' in results else None,
                    "metadata": results['metadatas'][0][i] if 'metadatas' in results else {},
                    "document": results['documents'][0][i] if 'documents' in results else ""
                })
        
        return formatted_results
    
    def find_similar_lore(self, lore: Lore, n_results: int = 5) -> List[Dict[str, Any]]:
        """Find lore similar to the given lore (for contradiction detection).
        
        Args:
            lore: Lore entity to find similar items for
            n_results: Number of results to return
        
        Returns:
            List of similar lore items
        """
        # Use the lore content as query
        return self.search_lore(
            query=lore.content,
            n_results=n_results + 1,  # +1 because it might return itself
            category=lore.category  # Search within same category
        )

    def compute_semantic_similarity(self, text_a: str, text_b: str) -> float:
        """Compute semantic similarity between two texts using embeddings.
        
        Uses a temporary collection to embed both texts and compute distance.
        Returns a score from 0.0 (dissimilar) to 1.0 (identical).
        
        Args:
            text_a: First text (e.g., beat description)
            text_b: Second text (e.g., scene content)
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            # Create a temporary collection for comparison
            # ChromaDB requires names to start with alphanumeric
            temp_collection = self.client.get_or_create_collection(
                name="temp_similarity_calc",
                metadata={"description": "Temporary collection for similarity computation"}
            )
            
            # Clear any existing data
            try:
                temp_collection.delete(ids=["text_a", "text_b"])
            except:
                pass
            
            # Add both texts
            temp_collection.add(
                ids=["text_a"],
                documents=[text_a]
            )
            
            # Query with text_b to get distance to text_a
            results = temp_collection.query(
                query_texts=[text_b],
                n_results=1
            )
            
            # Clean up
            try:
                self.client.delete_collection("temp_similarity_calc")
            except:
                pass
            
            # Extract distance and convert to similarity
            distances = results.get("distances", [[]])[0]
            if distances:
                distance = distances[0]
                # ChromaDB uses L2 distance by default
                # Convert to 0-1 similarity (lower distance = higher similarity)
                # Cap at 2.0 for normalization (typical L2 distances are 0-2 for normalized embeddings)
                similarity = max(0.0, 1.0 - (distance / 2.0))
                return round(similarity, 3)
            
            return 0.0
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Semantic similarity computation failed: {e}")
            return 0.0


def rebuild_indexes(project_dir: Path) -> None:
    """从实体 JSON 文件重建全部 ChromaDB 索引。

    用于 git checkout/reset 后恢复——tree 快照不含二进制 ChromaDB 文件。
    实体 JSON 文本文件是数据源，向量从文本重新计算，不会丢失信息。
    """
    import logging
    logger = logging.getLogger(__name__)
    from .manager import MemoryManager

    memory = MemoryManager(project_dir)
    vs = VectorStore(project_dir)
    count = 0

    for cid in memory.list_characters():
        c = memory.load_character(cid)
        if c:
            try:
                vs.index_character(c)
                count += 1
            except Exception as e:
                logger.warning("重建角色索引失败 %s: %s", cid, e)

    for lid in memory.list_locations():
        loc = memory.load_location(lid)
        if loc:
            try:
                vs.index_location(loc)
                count += 1
            except Exception as e:
                logger.warning("重建地点索引失败 %s: %s", lid, e)

    for fid in memory.list_factions():
        fac = memory.load_faction(fid)
        if fac:
            try:
                vs.index_faction(fac)
                count += 1
            except Exception as e:
                logger.warning("重建势力索引失败 %s: %s", fid, e)

    for sid in memory.list_scenes():
        scene = memory.load_scene(sid)
        if scene:
            try:
                vs.index_scene(scene)
                count += 1
            except Exception as e:
                logger.warning("重建场景索引失败 %s: %s", sid, e)

    for loop in memory.load_open_loops():
        try:
            vs.index_loop(loop)
            count += 1
        except Exception as e:
            logger.warning("重建线索索引失败: %s", e)

    for lore in memory.load_all_lore():
        try:
            vs.index_lore(lore)
            count += 1
        except Exception as e:
            logger.warning("重建世界观索引失败: %s", e)

    logger.info("ChromaDB 索引重建完成: %d 条", count)
