from app.services.qdrant_service import qdrant_service
from qdrant_client.http import models

try:
    if not qdrant_service.is_enabled:
        print("Qdrant not configured")
        exit(1)
    
    client = qdrant_service.client
    collection_name = qdrant_service.collection_name
    
    print(f"=== QDRANT COLLECTION DIAGNOSTICS ===\n")
    
    # Get collection info
    info = client.get_collection(collection_name)
    print(f"Collection: {collection_name}")
    print(f"Total points: {info.points_count}")
    print(f"Vector size: {info.config.params.vectors.size}")
    
    # Try to list all unique research_ids
    print(f"\n=== RESEARCH IDS IN QDRANT ===")
    
    # Scroll through all points
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
    
    # Extract unique research_ids
    research_ids = set()
    for point in all_points:
        rid = point.payload.get("research_id")
        if rid:
            research_ids.add(rid)
    
    print(f"Unique research_ids found: {sorted(research_ids)}")
    print(f"Total unique researches: {len(research_ids)}")
    print(f"Total chunks (points): {len(all_points)}")
    
    # Check for research_id index
    print(f"\n=== PAYLOAD SCHEMA ===")
    # The schema info might not be directly available, but we can try another approach
    # Try to search with a filter using research_id
    try:
        # If this works, the index exists
        sample_search = client.query_points(
            collection_name=collection_name,
            query=all_points[0].vector if all_points else [0] * 1536,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="research_id",
                        match=models.MatchAny(any=[list(research_ids)[0]]) if research_ids else [],
                    )
                ]
            ),
            limit=1,
        )
        print("✓ research_id index is working (query_filter successful)")
    except Exception as e:
        print(f"✗ research_id index issue: {e}")
    
    print(f"\n=== SAMPLE POINTS ===")
    for i, point in enumerate(all_points[:3]):
        print(f"Point {i}:")
        print(f"  ID: {point.id}")
        print(f"  research_id: {point.payload.get('research_id')}")
        print(f"  title: {point.payload.get('title')[:50]}...")
        print()
        
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
