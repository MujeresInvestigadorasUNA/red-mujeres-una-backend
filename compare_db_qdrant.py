from app.repositories.research_repository import ResearchRepository
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.services.qdrant_service import qdrant_service
from qdrant_client.http import models

try:
    db = SessionLocal()
    
    print("=== COMPARING DATABASE vs QDRANT ===\n")
    
    # Get all research from DB
    all_research = ResearchRepository.list_all(db)
    db_ids = set(r.id for r in all_research)
    print(f"[DB] Total research documents: {len(db_ids)}")
    print(f"     IDs: {sorted(db_ids)}")
    
    # Get all research from Qdrant
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
    print(f"\n[QDRANT] Total research documents: {len(qdrant_ids)}")
    print(f"         IDs: {sorted(qdrant_ids)}")
    
    # Check differences
    in_db_not_qdrant = db_ids - qdrant_ids
    in_qdrant_not_db = qdrant_ids - db_ids
    
    if in_db_not_qdrant:
        print(f"\n[✗] IN DATABASE BUT NOT IN QDRANT: {sorted(in_db_not_qdrant)}")
        print("    These need to be synced!")
        for rid in sorted(in_db_not_qdrant):
            r = next((r for r in all_research if r.id == rid), None)
            if r:
                print(f"      - ID {rid}: {r.title[:50]}")
    else:
        print(f"\n[✓] All DB research are in Qdrant")
    
    if in_qdrant_not_db:
        print(f"\n[⚠] IN QDRANT BUT NOT IN DATABASE: {sorted(in_qdrant_not_db)}")
        print("    Orphaned chunks (may be stale)")
    
    db.close()
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
