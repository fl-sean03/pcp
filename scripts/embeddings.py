#!/usr/bin/env python3
"""
Embeddings Module - Semantic search using ChromaDB for PCP.

Provides vector embedding storage and similarity search for captures.
Uses ChromaDB's built-in embedding function for simplicity.
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("Warning: chromadb not installed. Semantic search disabled.")

# Paths
VAULT_PATH = "/workspace/vault/vault.db"
CHROMA_PATH = "/workspace/vault/chroma_db"

if not os.path.exists(os.path.dirname(VAULT_PATH)):
    VAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "vault", "vault.db")
    CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "vault", "chroma_db")

# Ensure chroma directory exists
os.makedirs(CHROMA_PATH, exist_ok=True)

# Global client and collection (lazy initialized)
_chroma_client = None
_collection = None


def get_chroma_client():
    """Get or create ChromaDB client."""
    global _chroma_client

    if not CHROMADB_AVAILABLE:
        return None

    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False)
        )
    return _chroma_client


def get_collection():
    """Get or create the PCP captures collection."""
    global _collection

    client = get_chroma_client()
    if client is None:
        return None

    if _collection is None:
        _collection = client.get_or_create_collection(
            name="pcp_captures",
            metadata={"description": "PCP capture embeddings for semantic search"}
        )
    return _collection


def store_embedding(
    capture_id: int,
    text: str,
    capture_type: str = "note",
    metadata: Optional[Dict] = None
) -> bool:
    """
    Store an embedding for a capture in ChromaDB.

    Args:
        capture_id: The capture ID from SQLite
        text: The text content to embed
        capture_type: Type of capture (note, task, idea, decision, etc.)
        metadata: Additional metadata to store

    Returns:
        True if successful, False otherwise
    """
    collection = get_collection()
    if collection is None:
        return False

    try:
        # Build metadata
        doc_metadata = {
            "capture_id": capture_id,
            "capture_type": capture_type,
            "created_at": datetime.now().isoformat()
        }
        if metadata:
            # Sanitize metadata - ChromaDB only accepts str, int, float, bool, None
            for key, value in metadata.items():
                if isinstance(value, (list, dict)):
                    # Convert lists/dicts to JSON strings
                    import json
                    doc_metadata[key] = json.dumps(value)
                elif isinstance(value, (str, int, float, bool)) or value is None:
                    doc_metadata[key] = value
                else:
                    doc_metadata[key] = str(value)

        # Use capture_id as document ID
        doc_id = f"capture_{capture_id}"

        # Upsert to handle both new and updated captures
        collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[doc_metadata]
        )
        return True
    except Exception as e:
        print(f"Error storing embedding for capture {capture_id}: {e}")
        return False


def search_similar(
    query: str,
    limit: int = 10,
    capture_types: Optional[List[str]] = None,
    min_score: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Search for similar captures using semantic similarity.

    Args:
        query: The search query
        limit: Maximum number of results
        capture_types: Optional filter by capture types
        min_score: Minimum similarity score (0.0-1.0, higher is more similar)

    Returns:
        List of matches with capture_id, content preview, similarity score
    """
    collection = get_collection()
    if collection is None:
        return []

    try:
        # Build where filter if capture_types specified
        where_filter = None
        if capture_types:
            where_filter = {"capture_type": {"$in": capture_types}}

        # Query ChromaDB
        results = collection.query(
            query_texts=[query],
            n_results=limit,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        # Process results
        matches = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                # ChromaDB returns distance (lower is better), convert to similarity score
                distance = results['distances'][0][i] if results['distances'] else 0
                # Normalize distance to similarity (assuming cosine distance)
                similarity = max(0, 1 - distance)

                if similarity >= min_score:
                    matches.append({
                        "doc_id": doc_id,
                        "capture_id": results['metadatas'][0][i].get('capture_id'),
                        "capture_type": results['metadatas'][0][i].get('capture_type'),
                        "content_preview": results['documents'][0][i][:200] if results['documents'][0][i] else "",
                        "similarity": round(similarity, 3),
                        "metadata": results['metadatas'][0][i]
                    })

        return matches
    except Exception as e:
        print(f"Error in semantic search: {e}")
        return []


def get_embedding_stats() -> Dict[str, Any]:
    """Get statistics about the embedding collection."""
    collection = get_collection()
    if collection is None:
        return {"status": "unavailable", "count": 0}

    try:
        count = collection.count()
        return {
            "status": "available",
            "count": count,
            "collection_name": "pcp_captures",
            "path": CHROMA_PATH
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "count": 0}


def delete_embedding(capture_id: int) -> bool:
    """Delete an embedding by capture ID."""
    collection = get_collection()
    if collection is None:
        return False

    try:
        doc_id = f"capture_{capture_id}"
        collection.delete(ids=[doc_id])
        return True
    except Exception as e:
        print(f"Error deleting embedding for capture {capture_id}: {e}")
        return False


def rebuild_embeddings(limit: int = None) -> Dict[str, Any]:
    """
    Rebuild all embeddings from existing captures.
    Useful for initial setup or reindexing.

    Args:
        limit: Optional limit on number of captures to process

    Returns:
        Summary of rebuild operation
    """
    collection = get_collection()
    if collection is None:
        return {"success": False, "error": "ChromaDB not available"}

    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    # Get captures to embed
    query = """
        SELECT id, content, capture_type, created_at
        FROM captures_v2
        WHERE content IS NOT NULL AND content != ''
        ORDER BY created_at DESC
    """
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    success_count = 0
    error_count = 0

    for row in rows:
        capture_id, content, capture_type, created_at = row

        success = store_embedding(
            capture_id=capture_id,
            text=content,
            capture_type=capture_type or "note",
            metadata={"original_created_at": created_at}
        )

        if success:
            success_count += 1
        else:
            error_count += 1

    return {
        "success": True,
        "processed": len(rows),
        "embedded": success_count,
        "errors": error_count
    }


def hybrid_search(
    query: str,
    limit: int = 10,
    semantic_weight: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Combine semantic search with keyword search for better results.

    Args:
        query: Search query
        limit: Maximum results
        semantic_weight: Weight for semantic results (0.0-1.0)

    Returns:
        Combined and deduplicated results
    """
    # Get semantic results
    semantic_results = search_similar(query, limit=limit * 2)

    # Get keyword results from SQLite
    conn = sqlite3.connect(VAULT_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, content, capture_type, created_at
        FROM captures_v2
        WHERE content LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (f"%{query}%", limit * 2))

    keyword_results = []
    for row in cursor.fetchall():
        keyword_results.append({
            "capture_id": row[0],
            "content_preview": row[1][:200] if row[1] else "",
            "capture_type": row[2],
            "created_at": row[3],
            "keyword_match": True
        })
    conn.close()

    # Combine and score results
    combined = {}

    # Add semantic results with weighted score
    for r in semantic_results:
        cap_id = r.get("capture_id")
        if cap_id:
            combined[cap_id] = {
                **r,
                "combined_score": r.get("similarity", 0) * semantic_weight,
                "has_semantic": True,
                "has_keyword": False
            }

    # Add/update keyword results
    keyword_weight = 1 - semantic_weight
    for r in keyword_results:
        cap_id = r.get("capture_id")
        if cap_id in combined:
            combined[cap_id]["combined_score"] += keyword_weight
            combined[cap_id]["has_keyword"] = True
        else:
            combined[cap_id] = {
                **r,
                "combined_score": keyword_weight,
                "has_semantic": False,
                "has_keyword": True
            }

    # Sort by combined score and return top results
    sorted_results = sorted(
        combined.values(),
        key=lambda x: x.get("combined_score", 0),
        reverse=True
    )

    return sorted_results[:limit]


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python embeddings.py stats          - Show embedding statistics")
        print("  python embeddings.py rebuild [N]    - Rebuild embeddings (optional limit N)")
        print("  python embeddings.py search <query> - Search for similar captures")
        print("  python embeddings.py hybrid <query> - Hybrid semantic+keyword search")
        sys.exit(1)

    command = sys.argv[1]

    if command == "stats":
        stats = get_embedding_stats()
        print(json.dumps(stats, indent=2))

    elif command == "rebuild":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        print(f"Rebuilding embeddings{f' (limit: {limit})' if limit else ''}...")
        result = rebuild_embeddings(limit=limit)
        print(json.dumps(result, indent=2))

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python embeddings.py search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        results = search_similar(query)
        print(f"\nSemantic search for: '{query}'\n")
        for r in results:
            print(f"[{r['capture_type']}] (score: {r['similarity']}) {r['content_preview'][:80]}...")

    elif command == "hybrid":
        if len(sys.argv) < 3:
            print("Usage: python embeddings.py hybrid <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        results = hybrid_search(query)
        print(f"\nHybrid search for: '{query}'\n")
        for r in results:
            sources = []
            if r.get('has_semantic'):
                sources.append('semantic')
            if r.get('has_keyword'):
                sources.append('keyword')
            print(f"[{r.get('capture_type', 'unknown')}] ({', '.join(sources)}) {r.get('content_preview', '')[:80]}...")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
