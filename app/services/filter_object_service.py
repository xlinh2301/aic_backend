from typing import List, Dict, Optional

def map_filtered_to_clip(filtered_results: List[Dict], clip_results: List[Dict]) -> List[Dict]:
    """
    Map filtered object results to corresponding clip results.

    Parameters:
    - filtered_results: List of results filtered by object.
    - clip_results: List of clip results.

    Returns:
    - List of filtered clip results.
    """
    mapped_results = []
    
    for filtered in filtered_results:
        frame_id = filtered.get('frame_id')
        video_id = filtered.get("video_id")
        print("Frame ID of object: ", frame_id)
        print("Video ID of object: ", video_id)
        
        # Tìm kết quả trong clip dựa trên frame_id và video_id
        for clip in clip_results:
            if clip.get("frame_id") == frame_id and clip.get("video_id") == video_id:
                mapped_results.append(clip)
    
    return mapped_results

