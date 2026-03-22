from sqlalchemy import text
from app.core.db import SessionLocal
from app.services.research_service import research_service
from app.services.qdrant_service import qdrant_service
import json
from app.services.blob_storage_service import blob_storage_service

try:
    db = SessionLocal()
    
    print("=== SYNCING UNSYNCED RESEARCH TO QDRANT ===\n")
    
    # Get all research from DB
    result = db.execute(text("""
        SELECT r.id, r.title, r.description, r.keywords, r.research_link
        FROM research r
        ORDER BY r.id
    """))
    db_research = result.fetchall()
    db_ids = set(r[0] for r in db_research)
    
    # Get synced research from Qdrant
    client = qdrant_service.client
    collection_name = qdrant_service.collection_name
    
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
    
    qdrant_ids = set(p.payload.get("research_id") for p in all_points)
    unsynced_ids = db_ids - qdrant_ids
    
    print(f"Total research in DB: {len(db_ids)}")
    print(f"Total research in Qdrant: {len(qdrant_ids)}")
    print(f"Unsynced research: {len(unsynced_ids)}")
    print(f"Unsynced IDs: {sorted(unsynced_ids)}\n")
    
    # Sync each unsynced research
    synced_count = 0
    failed_count = 0
    
    for research in db_research:
        rid, title, description, keywords, research_link = research
        if rid in unsynced_ids:
            try:
                print(f"[{synced_count + failed_count + 1}/{len(unsynced_ids)}] Syncing ID {rid}: {title[:40]}...", end=" ")
                
                # Sync to Qdrant using the service method
                research_service._sync_research_embeddings_to_qdrant(db, rid)
                
                synced_count += 1
                print("✓")
            except Exception as e:
                failed_count += 1
                print(f"✗ Error: {str(e)[:50]}")
    
    print(f"\n=== SYNC COMPLETE ===")
    print(f"Successfully synced: {synced_count}/{len(unsynced_ids)}")
    
    if failed_count > 0:
        print(f"Failed: {failed_count}")
    
    # Verify
    print("\n=== VERIFICATION ===")
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
    
    qdrant_ids_after = set(p.payload.get("research_id") for p in all_points)
    print(f"Research in Qdrant after sync: {len(qdrant_ids_after)}")
    print(f"IDs: {sorted(qdrant_ids_after)}")
    
    db.close()
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
