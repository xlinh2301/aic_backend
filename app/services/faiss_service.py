from typing import List, Dict, Any, Optional
import torch
import clip
import os
import numpy as np
import json
import faiss
from googletrans import Translator
from langdetect import detect
from PIL import Image
from pydantic import BaseModel
from app.config import INDEX_FILE_PATH, ID_MAP_FILE_PATH, FILE_LIST

# Cấu hình môi trường và tải mô hình CLIP
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
translator = Translator()

class SearchResult(BaseModel):
    frame_id: int
    video_id: str
    video_folder: str
    image_path: str

def translate_query(query: str) -> str:
    """Dịch câu truy vấn từ tiếng Việt sang tiếng Anh"""
    translated_query = translator.translate(query, src='vi', dest='en').text
    print(f"Translated query: {translated_query}")
    return translated_query

def detect_language(query: str) -> Optional[str]:
    """Nhận diện ngôn ngữ của câu truy vấn"""
    try:
        lang = detect(query)
        print(f"Detected language: {lang}")
        return lang
    except Exception as e:
        print(f"Language detection failed: {e}")
        return None

def process_image(image_path: str) -> torch.Tensor:
    """Tải và tiền xử lý hình ảnh cho mô hình CLIP"""
    image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
    return image

def search_text(text_query: str, index, top_k: int = 5) -> List[int]:
    """Tìm kiếm văn bản, dịch nếu cần thiết và thực hiện tìm kiếm"""
    lang = detect_language(text_query)

    if lang == "vi":
        # Dịch tiếng Việt sang tiếng Anh
        translated_query = translate_query(text_query)
    else:
        # Sử dụng văn bản gốc nếu không phải tiếng Việt
        translated_query = text_query

    text = clip.tokenize([translated_query]).to(device)
    with torch.no_grad():
        text_features = model.encode_text(text)
    text_features = text_features.cpu().numpy().astype('float32').flatten()
    distances, indices = index.search(np.expand_dims(text_features, axis=0), top_k)
    print(f"Search distances (text): {distances}")
    print(f"Search indices (text): {indices}")
    return indices[0]

def search_image(image_path: str, index, top_k: int = 5) -> List[int]:
    """Tìm kiếm bằng hình ảnh"""
    image = process_image(image_path)
    with torch.no_grad():
        image_features = model.encode_image(image)
    image_features = image_features.cpu().numpy().astype('float32').flatten()
    distances, indices = index.search(np.expand_dims(image_features, axis=0), top_k)
    return indices[0]

def load_file_list(file_list_path: str) -> Dict[str, str]:
    """Tải tệp JSON chứa ID và tên tệp vào một dictionary."""
    with open(file_list_path, 'r') as f:
        file_list = json.load(f)
    # Tạo một dictionary từ ID và tên tệp
    return {file['title']: file['id'] for file in file_list}

def construct_image_path(file_list: Dict[str, str], image_info: Dict[str, str]) -> Optional[str]:
    """
    Xây dựng đường dẫn ảnh từ thông tin ảnh sử dụng tệp JSON chứa ID và tên tệp.
    
    :param file_list: Dictionary chứa ID và tên tệp.
    :param image_info: Thông tin ảnh bao gồm 'frame_id', 'video_id', và 'video_folder'.
    :return: Đường dẫn trực tiếp đến file ảnh trên Google Drive.
    """
    base_url = "https://drive.google.com/uc?export=view&id="
    
    # Extract information from image_info
    frame_id = image_info.get('frame_id')
    video_id = image_info.get('video_id')
    video_folder = image_info.get('video_folder')
    
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

def search_faiss(query: Optional[str] = None, image_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Tìm kiếm trong FAISS dựa trên văn bản hoặc hình ảnh và trả về kết quả dưới dạng danh sách từ điển"""
    # Tải chỉ mục FAISS và bản đồ ID
    index_load = faiss.read_index(INDEX_FILE_PATH)
    
    # Đọc bản đồ ID từ tệp
    try:
        with open(ID_MAP_FILE_PATH, 'r') as f:
            id_map_load = json.load(f)
        
        # Đảm bảo id_map_load là một dictionary
        if isinstance(id_map_load, list):
            id_map_load = {str(i): item for i, item in enumerate(id_map_load)}
        
        # Tải danh sách tệp từ Google Drive
        file_list = load_file_list(FILE_LIST)  # Thay đổi đường dẫn đến tệp danh sách tệp
        
    except Exception as e:
        print(f"Error loading ID map file: {e}")
        return []

    if query:
        # Tìm kiếm theo văn bản
        result_indices = search_text(query, index_load, 200)
    elif image_path:
        # Tìm kiếm theo hình ảnh
        result_indices = search_image(image_path, index_load, 200)
    else:
        raise ValueError("Either query or image_path must be provided.")

    # Chuyển đổi các chỉ số thành kết quả và xây dựng đường dẫn hình ảnh
    results = []
    for idx in result_indices:
        image_info = id_map_load.get(str(idx), None)
        if image_info:
            # Sử dụng hàm construct_image_path để tạo đường dẫn hình ảnh
            img_path = construct_image_path(file_list, image_info)
            if img_path:
                # Thêm thông tin hình ảnh và đường dẫn hình ảnh vào kết quả
                results.append({
                    'frame_id': image_info['frame_id'],
                    'video_id': image_info['video_id'],
                    'video_folder': image_info['video_folder'],
                    'image_path': img_path
                })
            else:
                print(f"Failed to construct image path for index {idx}")

    return results

# # Ví dụ sử dụng hàm search_faiss
# folder_id = '14aa9fYPRS0h8wpB_oHEEGerhuFPue8sN'  # Thay bằng ID của thư mục Dataset_train
# query = "lũ lụt"  # Câu truy vấn tìm kiếm

# # Gọi hàm search_faiss với đối số drive và folder_id
# search_result = search_faiss(query=query)
# print(search_result)
