from app.services.qdrant_service import qdrant_service
from qdrant_client.http import models

try:
    client = qdrant_service.client
    collection_name = qdrant_service.collection_name
    
    print("=== TEST SEARCH: user 5 recent visits (5, 6, 7, 8, 10) ===\n")
    
    visited_ids = [5, 6, 7, 8, 10]
    
    # Step 1: Scroll for visited research
    print(f"[1] Fetching embeddings for visited research_ids: {visited_ids}")
    results = client.scroll(
        collection_name=collection_name,
        limit=1000,
        with_payload=True,
        with_vectors=True,
        scroll_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="research_id",
                    match=models.MatchAny(any=visited_ids),
                )
            ]
        ),
    )
    
    points = results[0]
    print(f"    Found {len(points)} chunks from visited research")
    
    if points:
        # Step 2: Calculate centroid
        embeddings = [p.vector for p in points if p.vector]
        print(f"\n[2] Computing centroid from {len(embeddings)} embeddings")
        centroid = [sum(dim) / len(embeddings) for dim in zip(*embeddings)]
        print(f"    Centroid size: {len(centroid)}")
        
        # Step 3: Search for similar excluding visited
        print(f"\n[3] Searching for similar docs (excluding visited research_ids)")
        search_results = client.query_points(
            collection_name=collection_name,
            query=centroid,
            query_filter=models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="research_id",
                        match=models.MatchAny(any=visited_ids),
                    )
                ]
            ),
            limit=20,
        )
        
        print(f"    Found {len(search_results.points)} similar chunks")
        
        # Deduplicate by research_id
        seen_ids = set()
        unique_results = []
        for point in search_results.points:
            rid = point.payload.get("research_id")
            if rid not in seen_ids:
                seen_ids.add(rid)
                unique_results.append(point)
                print(f"      [{len(unique_results)}] research_id={rid}, title={point.payload.get('title')[:40]}..., score={point.score:.4f}")
        
        print(f"\n[✓] Unique documents found: {len(unique_results)}")
    else:
        print("[✗] No visited research found!")
        
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
