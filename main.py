from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
from app.services.faiss_service import search_faiss, search_image
from app.services.elasticsearch_service import search_ocr, search_object, search_asr
from app.services.filter_metadata_service import filter_by_metadata  # Import directly
from elasticsearch import Elasticsearch
from datetime import datetime

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Elasticsearch
es = Elasticsearch(['http://localhost:9200'])

@app.post("/app/search")
async def search_all(
    queries: Dict[str, Optional[str]], 
    top: Optional[int] = 10, 
    operator: Optional[str] = "gte", 
    value: Optional[int] = 1, 
    publish_day: Optional[int] = None,
    publish_month: Optional[int] = None,
    publish_year: Optional[int] = None
):
    """
    Endpoint to perform combined search from multiple sources: CLIP, OCR, Object, ASR, and Image.

    Parameters:
    - queries: Dictionary containing queries for CLIP, OCR, Object, ASR, and Image.
    - top: Maximum number of results to return for object queries.
    - operator: Comparison operator for the range condition in object queries. Can be "gte", "gt", "lte", "lt", or "eq".
    - value: Value of label_count to compare in the object query.
    - publish_day: Day of the publish date to filter results.
    - publish_month: Month of the publish date to filter results.
    - publish_year: Year of the publish date to filter results.

    Returns:
    - Combined search results from various sources.
    """
    results = {
        "clip": [],
        "ocr": [],
        "object": [],
        "asr": [],
        "image": []
    }

    try:
        # Perform searches in respective services
        if "clip" in queries and queries["clip"]:
            results["clip"] = search_faiss(queries["clip"])

        if "ocr" in queries and queries["ocr"]:
            results["ocr"] = search_ocr(es, "ocr", queries["ocr"])

        if "object" in queries and queries["object"]:
            results["object"] = search_object(es, "object_detection", queries["object"], top, operator, value)

        if "asr" in queries and queries["asr"]:
            results["asr"] = search_asr(es, "asr_test", queries["asr"])

        if "image_url" in queries and queries["image_url"]:
            results["image"] = search_image(queries["image_url"])

        # Combine search results
        combined_results = combine_results(results)

        # Filter results by publish_date if any date components are provided
        if publish_day or publish_month or publish_year:
            # Construct the publish_date to use for filtering
            try:
                publish_date = datetime(
                    year=publish_year if publish_year else 1, 
                    month=publish_month if publish_month else 1, 
                    day=publish_day if publish_day else 1
                ).date()  # Use .date() to get just the date part
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date provided.")
            
            publish_day = publish_day if publish_day else None
            publish_month = publish_month if publish_month else None
            publish_year = publish_year if publish_year else None

            # Filter results by publish_date
            for key in combined_results:
                if queries.get(key):
                    combined_results[key] = filter_by_metadata(combined_results, key, publish_day, publish_month, publish_year)

        return combined_results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def combine_results(results: Dict[str, list]) -> Dict[str, list]:
    """
    Combine search results from various sources.

    Parameters:
    - results: Dictionary containing search results from CLIP, OCR, Object, ASR, and Image.

    Returns:
    - Dictionary containing combined results from various sources.
    """
    combined = {
        "clip": results["clip"],
        "ocr": results["ocr"],
        "object": results["object"],
        "asr": results["asr"],
        "image": results["image"]
    }
    return combined
