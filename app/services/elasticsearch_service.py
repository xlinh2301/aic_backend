from typing import List, Dict
from elasticsearch import Elasticsearch, exceptions
import json
import os
from typing import Optional
from rapidfuzz import fuzz # type: ignore
from app.config import ASR_BACKUP_FILE_PATH, OCR_BACKUP_FILE_PATH, OBJECT_BACKUP_FILE_PATH, FILE_LIST

def load_file_list(file_list_path: str) -> Dict[str, str]:
    """Tải tệp JSON chứa ID và tên tệp vào một dictionary."""
    with open(file_list_path, 'r') as f:
        file_list = json.load(f)
    # Tạo một dictionary từ ID và tên tệp
    return {file['title']: file['id'] for file in file_list}

def construct_image_path(file_list: Dict[str, str], image_info: Dict[str, str], frame_id: str, video_id: str, video_folder: str) -> Optional[str]:
    """
    Xây dựng đường dẫn ảnh từ thông tin ảnh sử dụng tệp JSON chứa ID và tên tệp.
    
    :param file_list: Dictionary chứa ID và tên tệp.
    :param image_info: Thông tin ảnh bao gồm 'frame_id', 'video_id', và 'video_folder'.
    :return: Đường dẫn trực tiếp đến file ảnh trên Google Drive.
    """
    base_url = "https://drive.google.com/thumbnail?export=view&id="
    
    if frame_id and video_id and video_folder:
        # Build the file name
        file_name = f"{video_id}_{frame_id}.jpg"
        
        # Get the file ID from the file name using the file_list dictionary
        file_id = file_list.get(file_name)
        if file_id:
            # Build the image path from file_id
            image_path = f"{base_url}{file_id}"
            return image_path
        else:
            print(f"File ID not found for file: {file_name}")
            return None
    else:
        print(f"Required information not found in image_info: {image_info}")
        return None


# Helper function to load backup data
def load_backup_data(backup_path: str) -> List[Dict]:
    data = []
    try:
        with open(backup_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:  
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    print(f"JSON decoding error: {e}")
    except FileNotFoundError:
        print(f"File not found: {backup_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return data

def search_ocr_from_elasticsearch(es: Elasticsearch, index_name: str, query: str, file_list: Dict[str, str]) -> List[Dict]:
    search_query = {
        "query": {
            "match": {
                "text": query
            }
        }
    }
    response = es.search(index=index_name, body=search_query)
    hits = response['hits']['hits']
    
    # Add image path to each result
    for hit in hits:
        frame_id = hit['_source'].get('frame', {})
        video_id = hit['_source'].get('video_name', {})
        video_folder = f"Videos_{video_id.split('_')[0]}"
        image_path = construct_image_path(file_list, hits, frame_id, video_id, video_folder)
        hit['_source']['image_path'] = image_path
    
    return hits

def search_ocr_in_backup(query: str, backup_data: List[List[Dict]], file_list: Dict[str, str], threshold: int = 70) -> List[Dict]:
    results = []

    # Iterate through the list of lists
    for entry_list in backup_data:
        for entry in entry_list:
            text_list = entry.get('text', [])
            if isinstance(text_list, list):
                for text in text_list:
                    score = fuzz.partial_ratio(query.lower(), text.lower())
                    if score >= threshold:
                        # Add image path to the result
                        frame_name = entry['file']
                        frame_id = frame_name.split('_')[-1].split('.')[0]
                        video_id = entry['video_name']
                        video_folder = f"Videos_{video_id.split('_')[0]}"
                        image_path = construct_image_path(file_list, entry, frame_id, video_id, video_folder)
                        entry['image_path'] = image_path
                        results.append(entry)
                        break  # Stop after finding the first match in the list

            if len(results) >= 200:  # Limit the number of results
                break
    
    return results

def search_ocr(es: Elasticsearch, index_name: str, query: str) -> List[Dict]:
    file_list = load_file_list(FILE_LIST)
    backup_data = load_backup_data(OCR_BACKUP_FILE_PATH)
    try:

        es_results = search_ocr_from_elasticsearch(es, index_name, query, file_list)
        if es_results:
            return es_results
        else:
            print("Error: No results from Elasticsearch")
            return search_ocr_in_backup(query, backup_data, file_list, threshold=50)
    except (exceptions.ConnectionError, exceptions.TransportError) as e:
        print(f"Elasticsearch connection error: {e}")
        return search_ocr_in_backup(query, backup_data, file_list, threshold=50)

# ASR search functions
def search_asr_from_elasticsearch(es: Elasticsearch, index_name: str, query: str) -> List[Dict]:
    search_query = {
        "query": {
            "match": {
                "text": query
            }
        }
    }
    response = es.search(index=index_name, body=search_query)
    hits = response['hits']['hits']
    return hits

def search_asr_in_backup(query: str, backup_data: List[Dict], threshold: int = 70) -> List[Dict]:
    results = []
    
    for entry in backup_data:
        text = entry.get('text', '')
        # Perform fuzzy matching
        score = fuzz.partial_ratio(query.lower(), text.lower())
        if score >= threshold:  
            results.append(entry)
        
        if len(results) >= 200:
            break
    
    return results

def search_asr(es: Elasticsearch, index_name: str, query: str) -> List[Dict]:
    try:
        es_results = search_asr_from_elasticsearch(es, index_name, query)
        if es_results:
            return es_results
        else:
            print("Error: No results from Elasticsearch")
            backup_data = load_backup_data(ASR_BACKUP_FILE_PATH)
            return search_asr_in_backup(query, backup_data, threshold=50)
    except (exceptions.ConnectionError, exceptions.TransportError) as e:
        print(f"Elasticsearch connection error: {e}")
        backup_data = load_backup_data(ASR_BACKUP_FILE_PATH)
        return search_asr_in_backup(query, backup_data, threshold=50)

# Object search functions (already provided)
def search_object_from_elasticsearch(es: Elasticsearch, index_name: str, query: str, top: int, operator: str, value: int) -> List[Dict]:
    file_list = load_file_list(FILE_LIST)
    
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
                    }
                ]
            }
        },
        "size": top
    }
    
    try:
        response = es.search(index=index_name, body=search_body)
        hits = response['hits']['hits']
        
        # Add image path to each result
        for hit in hits:
            frame_id = hit['_source'].get('frame_id', {})
            video_id = hit['_source'].get('video_id', {})
            video_folder = hit['_source'].get('video_folder', {})
            image_path = construct_image_path(file_list, hits, frame_id, video_id, video_folder)
            hit['_source']['image_path'] = image_path
        return response['hits']['hits']
    except Exception as e:
        print(f"Error searching Elasticsearch: {str(e)}")
        return []

def search_object_in_backup(query: str, backup_data: List[Dict], top: int, operator: str, value: int) -> List[Dict]:
    results = []
    file_list = load_file_list(FILE_LIST)
    
    for entry in backup_data:
        if query.lower() in [name.lower() for name in entry['labels']]:
            count_value = entry['label_counts'].get(query, 0)
            
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

            frame_id = entry.get('frame_id', {})
            video_id = entry.get('video_id', {})
            video_folder = entry.get('video_folder', {})
            image_path = construct_image_path(file_list, entry, frame_id, video_id, video_folder)
            entry['image_path'] = image_path
            results.append(entry)
        
        if len(results) >= top:
            break

    return results

def search_object(es: Elasticsearch, index_name: str, query: str, top: int, operator: str, value: int) -> List[Dict]:
    es_results = search_object_from_elasticsearch(es, index_name, query, top, operator, value)
    if es_results:
        return es_results
    else:
        print("Error: Cannot connect to Elastic search server")
        backup_data = load_backup_data(OBJECT_BACKUP_FILE_PATH)
        backup_results = search_object_in_backup(query, backup_data, top, operator, value)
        return backup_results
