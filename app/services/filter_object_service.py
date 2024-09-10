from typing import List, Dict, Optional
from elasticsearch import Elasticsearch, exceptions
import json
from app.config import OBJECT_BACKUP_FILE_PATH, FILE_LIST
from rapidfuzz import fuzz # type: ignore
from app.services.elasticsearch_service import construct_image_path, load_file_list, load_backup_data

def search_filter_object_from_elasticsearch(
    es: Elasticsearch, 
    index_name: str, 
    query: str, 
    top: int, 
    operator: str, 
    value: int, 
    clip_results: List[Dict]
) -> List[Dict]:
    # Extract frame_ids and video_ids from clip results
    frame_ids = [clip['frame_id'] for clip in clip_results]
    video_ids = [clip['video_id'] for clip in clip_results]
    
    search_body = {
        "query": {
            "bool": {
                "must": [
                    {
                        "term": {
                            "labels.keyword": query
                        }
                    },
                    {
                        "range": {
                            f"label_counts.{query}": {
                                operator: value
                            }
                        }
                    },
                    {
                        "terms": {
                            "frame_id": frame_ids  # Only search within the provided frame_ids
                        }
                    },
                    {
                        "terms": {
                            "video_id": video_ids  # Only search within the provided video_ids
                        }
                    }
                ]
            }
        },
        "size": top
    }
    
    try:
        response = es.search(index=index_name, body=search_body)
        hits = response['hits']['hits']
        results = []

        # Add image path to each result
        for hit in hits:
            frame_id = hit['_source'].get('frame_id', {})
            video_id = hit['_source'].get('video_id', {})
            video_folder = hit['_source'].get('video_folder', {})
            image_path = construct_image_path(file_list, hits, frame_id, video_id, video_folder)
            hit['_source']['image_path'] = image_path
            label_counts = hit['_source'].get('label_counts', {})
            labels = hit['_source'].get('labels', [])
            results.append(frame_id)
            results.append(video_id)
            results.append(video_folder)
            results.append(labels)
            results.append(label_counts)
            results.append(image_path)
        return results
    except Exception as e:
        print(f"Error searching Elasticsearch: {str(e)}")
        return []

def search_filter_object_in_backup(
    query: str, 
    backup_data: List[Dict], 
    top: int, 
    operator: str, 
    value: int, 
    clip_results: List[Dict]
) -> List[Dict]:
    results = []
    file_list = load_file_list(FILE_LIST)
    
    allowed_pairs = {(clip['frame_id'], clip['video_id']) for clip in clip_results}
    
    # Iterate through backup_data
    for entry in backup_data:
        entry_frame_id = entry.get('frame_id')
        entry_video_id = entry.get('video_id')
        
        # Check if the (frame_id, video_id) pair is in the allowed pairs
        if (entry_frame_id, entry_video_id) in allowed_pairs:
            if query.lower() in [name.lower() for name in entry.get('labels', [])]:
                count_value = entry['label_counts'].get(query, 0)

                # Apply the operator to filter based on the count_value
                if operator == 'lt' and count_value < value:
                    results.append(entry)
                elif operator == 'lte' and count_value <= value:
                    results.append(entry)
                elif operator == 'gt' and count_value > value:
                    results.append(entry)
                elif operator == 'gte' and count_value >= value:
                    results.append(entry)
                elif operator == 'eq' and count_value == value:
                    results.append(entry)

                # Add image path information
                frame_id = entry.get('frame_id', {})
                video_id = entry.get('video_id', {})
                video_folder = entry.get('video_folder', {})
                image_path = construct_image_path(file_list, entry, frame_id, video_id, video_folder)
                entry['image_path'] = image_path

                # Append the entry to the results
                results.append(entry)
        
        # Break when enough results are found
        if len(results) >= top:
            break

    return results

def search_filter_object(es: Elasticsearch, index_name: str, query: str, operator: str, value: int, clip_results: List[Dict]) -> List[Dict]:
    top = 200
    es_results = search_filter_object_from_elasticsearch(es, index_name, query, top, operator, value, clip_results)
    if es_results:
        print("Successfully connected to Elastic search server")
        return es_results
    else:
        print("Error: Cannot connect to Elastic search server")
        backup_data = load_backup_data(OBJECT_BACKUP_FILE_PATH)
        backup_results = search_filter_object_in_backup(query, backup_data, top, operator, value, clip_results)
        return backup_results