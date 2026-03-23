from sqlalchemy import text
from app.core.db import SessionLocal
from app.services.qdrant_service import qdrant_service

try:
    db = SessionLocal()
    
    print("=== COMPARING DATABASE vs QDRANT ===\n")
    
    # Get all research from DB using raw SQL
    result = db.execute(text("SELECT id, title FROM research ORDER BY id"))
    db_data = result.fetchall()
    db_ids = set(r[0] for r in db_data)
    print(f"[DB] Total research documents: {len(db_ids)}")
    print(f"     IDs: {sorted(db_ids)}")
    db_map = {r[0]: r[1] for r in db_data}
    
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
        print(f"\n[✗] IN DATABASE BUT NOT IN QDRANT (NEED SYNC): {sorted(in_db_not_qdrant)}")
        for rid in sorted(in_db_not_qdrant):
            print(f"      - ID {rid}: {db_map[rid][:50]}")
    else:
        print(f"\n[✓] All DB research are synced to Qdrant")
    
    if in_qdrant_not_db:
        print(f"\n[⚠] IN QDRANT BUT NOT IN DATABASE: {sorted(in_qdrant_not_db)}")
    
    db.close()
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
