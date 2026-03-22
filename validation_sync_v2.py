#!/usr/bin/env python
"""
Validation and auto-sync script for research documents between Database and Qdrant.
Run this periodically or after identifying sync issues.
"""
import json
from datetime import datetime
from sqlalchemy import text
from app.core.db import SessionLocal
from app.services.research_service import ResearchService
from app.services.qdrant_service import qdrant_service

def check_qdrant_health():
    """Verify Qdrant is accessible and configured."""
    print("\n=== QDRANT HEALTH CHECK ===")
    
    if not qdrant_service.is_enabled:
        print("❌ Qdrant is NOT enabled (missing QDRANT_ENDPOINT or QDRANT_API_KEY)")
        return False
    
    try:
        client = qdrant_service._require_client()
        if not client:
            print("❌ Qdrant client could not be initialized")
            return False
        
        # Check if collection exists
        exists = client.collection_exists(qdrant_service.collection_name)
        if exists:
            collection_info = client.get_collection(qdrant_service.collection_name)
            points_count = collection_info.points_count
            print(f"✓ Qdrant is healthy")
            print(f"  Collection: {qdrant_service.collection_name}")
            print(f"  Points: {points_count}")
            return True
        else:
            print(f"⚠ Collection '{qdrant_service.collection_name}' does not exist (will be created on first sync)")
            return True
    except Exception as e:
        print(f"❌ Qdrant health check failed: {e}")
        return False

def sync_missing_documents():
    """Find documents in DB but not in Qdrant and sync them."""
    print("\n=== CHECKING FOR UNSYNCED DOCUMENTS ===")
    
    db = SessionLocal()
    try:
        # Get all research from DB
        result = db.execute(text('''
            SELECT r.id, r.user_id, r.title, r.research_link, r.vector_link
            FROM research r
            ORDER BY r.id
        '''))
        db_research = result.fetchall()
        db_ids = set(r[0] for r in db_research)
        
        # Get synced research from Qdrant
        client = qdrant_service.client
        if not client:
            print("❌ Cannot check Qdrant - client not initialized")
            return 0
        
        collection_name = qdrant_service.collection_name
        
        # Initialize qdrant_ids
        qdrant_ids = set()
        
        # Scroll through all points in Qdrant
        try:
            all_points = []
            cursor = None
            while True:
                result = client.scroll(
                    collection_name=collection_name,
                    limit=100,
                    with_payload=True,
                    offset=cursor,
                )
                points, cursor = result
                all_points.extend(points)
                if not cursor:
                    break
            
            # Extract research IDs from all points
            qdrant_ids = set(p.payload.get("research_id") for p in all_points if p.payload.get("research_id"))
        except Exception as e:
            print(f"⚠ Collection doesn't exist yet or error scrolling: {e}")
            qdrant_ids = set()
        
        unsynced_ids = db_ids - qdrant_ids
        
        print(f"Database: {len(db_ids)} documents")
        print(f"Qdrant: {len(qdrant_ids)} documents")
        print(f"Unsynced: {len(unsynced_ids)} documents")
        
        if not unsynced_ids:
            print("✓ All documents are synced!")
            return 0
        
        print(f"Unsynced IDs: {sorted(unsynced_ids)}")
        
        # Sync unsynced documents
        print("\n=== SYNCING UNSYNCED DOCUMENTS ===")
        synced_count = 0
        failed_count = 0
        
        for research in db_research:
            rid, user_id, title, research_link, vector_link = research
            if rid in unsynced_ids:
                print(f"[{synced_count + failed_count + 1}/{len(unsynced_ids)}] ID {rid}: {title[:40]}...", end=" ", flush=True)
                try:
                    if not vector_link:
                        print("✗ No vector_link")
                        failed_count += 1
                        continue
                    
                    # Load vector payload
                    vector_payload = ResearchService._load_vector_payload(vector_link)
                    chunks = vector_payload.get("chunks", [])
                    embeddings = vector_payload.get("embeddings", [])
                    
                    if not chunks or not embeddings:
                        print("✗ No embeddings")
                        failed_count += 1
                        continue
                    
                    # Sync to Qdrant
                    ResearchService._sync_research_embeddings_to_qdrant(
                        research_id=rid,
                        user_id=user_id,
                        title=title,
                        research_link=research_link,
                        vector_link=vector_link,
                        chunks=chunks,
                        embeddings=embeddings,
                        created_at=datetime.utcnow().isoformat(),
                    )
                    
                    synced_count += 1
                    print("✓")
                except Exception as e:
                    failed_count += 1
                    print(f"✗ {str(e)[:50]}")
        
        print(f"\nResult: {synced_count} synced, {failed_count} failed")
        return synced_count
        
    finally:
        db.close()

def main():
    """Run all validation and sync checks."""
    print("=" * 60)
    print("RESEARCH DOCUMENTS - QDRANT SYNC VALIDATOR")
    print("=" * 60)
    print(f"Time: {datetime.utcnow().isoformat()}")
    
    # Check Qdrant health
    if not check_qdrant_health():
        print("\n❌ CRITICAL: Qdrant is not available. Cannot proceed with sync.")
        return
    
    # Sync missing documents
    synced = sync_missing_documents()
    
    print("\n" + "=" * 60)
    if synced > 0:
        print(f"✓ SUCCESS: Synced {synced} documents to Qdrant")
    else:
        print("✓ All documents are in sync")
    print("=" * 60)

if __name__ == "__main__":
    main()
