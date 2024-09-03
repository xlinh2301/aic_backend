from typing import List, Dict
from elasticsearch import Elasticsearch, exceptions
import json
from rapidfuzz import fuzz # type: ignore
from app.config import ASR_BACKUP_FILE_PATH, OCR_BACKUP_FILE_PATH, OBJECT_BACKUP_FILE_PATH

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

# OCR search functions
def search_ocr_from_elasticsearch(es: Elasticsearch, index_name: str, query: str) -> List[Dict]:
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

def search_ocr_in_backup(query: str, backup_data: List[Dict], threshold: int = 70) -> List[Dict]:
    results = []
    
    for entry in backup_data:
        text = entry.get('text', '')
        score = fuzz.partial_ratio(query.lower(), text.lower())
        print(score)
        if score >= threshold:  
            results.append(entry)
        
        if len(results) >= 200:
            break
    
    return results

def search_ocr(es: Elasticsearch, index_name: str, query: str) -> List[Dict]:
    try:
        es_results = search_ocr_from_elasticsearch(es, index_name, query)
        if es_results:
            return es_results
        else:
            print("Error: No results from Elasticsearch")
            backup_data = load_backup_data(OCR_BACKUP_FILE_PATH)
            return search_ocr_in_backup(query, backup_data, threshold=50)
    except (exceptions.ConnectionError, exceptions.TransportError) as e:
        print(f"Elasticsearch connection error: {e}")
        backup_data = load_backup_data(OCR_BACKUP_FILE_PATH)
        return search_ocr_in_backup(query, backup_data, threshold=50)
        return backup_results

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
        return response['hits']['hits']
    except Exception as e:
        print(f"Error searching Elasticsearch: {str(e)}")
        return []

def search_object_in_backup(query: str, backup_data: List[Dict], top: int, operator: str, value: int) -> List[Dict]:
    results = []
    
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
