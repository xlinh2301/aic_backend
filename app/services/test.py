import os
import json
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# Đảm bảo rằng đường dẫn đến tệp client_secrets.json là chính xác
client_secrets_path = "E:\\CODE\\AIC_2024\\Fastapi\\app\\data\\client_secrets.json"

if not os.path.exists(client_secrets_path):
    raise FileNotFoundError(f"Client secrets file not found at {client_secrets_path}")

# Cấu hình PyDrive và xác thực
gauth = GoogleAuth()
gauth.LoadClientConfigFile(client_secrets_path)
gauth.LocalWebserverAuth()  # Cho phép xác thực qua trình duyệt web

# Tạo đối tượng GoogleDrive
drive = GoogleDrive(gauth)

def get_file_info(drive, folder_id):
    """Lấy ID và tên các tệp trong thư mục con, bao gồm cả các thư mục con, loại trừ các tệp ZIP và MP4"""
    files_info = []
    seen_file_ids = set()  # Tập hợp để theo dõi các ID tệp đã được xử lý
    folders = [folder_id]
    
    while folders:
        current_folder_id = folders.pop()
        print(f"Đang xử lý thư mục: {current_folder_id}")
        query = f"'{current_folder_id}' in parents and trashed=false"
        page_token = None
        
        while True:
            params = {'q': query}
            if page_token:
                params['pageToken'] = page_token
            
            file_list = drive.ListFile(params).GetList()
            print(f"Đã tìm thấy {len(file_list)} tệp trong thư mục {current_folder_id}")
            for file in file_list:
                file_id = file['id']
                file_title = file['title']
                mime_type = file['mimeType']
                
                if file_id in seen_file_ids:
                    print(f"Tệp đã được xử lý: {file_title}")
                    continue  # Bỏ qua tệp đã được xử lý
                
                # Loại trừ các tệp ZIP và MP4
                if mime_type in ['application/zip', 'video/mp4']:
                    print(f"Bỏ qua tệp: {file_title}")
                    continue
                
                if mime_type == 'application/vnd.google-apps.folder':
                    folders.append(file_id)
                    print(f"Thêm thư mục con: {file_id}")
                else:
                    file_info = {
                        'id': file_id,
                        'title': file_title
                    }
                    files_info.append(file_info)
                    seen_file_ids.add(file_id)
                    print(f"Thêm tệp: {file_title}")
            
            # Lấy pageToken cho trang tiếp theo
            page_token = drive.auth.service.files().list(q=query, pageToken=page_token).execute().get('nextPageToken')
            if not page_token:
                break
    
    return files_info

def save_file_list_to_json(drive, folder_id, output_file_path):
    """Lưu danh sách các tệp vào tệp JSON chỉ chứa ID và tên"""
    files_info = get_file_info(drive, folder_id)
    
    # Lưu vào tệp JSON
    with open(output_file_path, 'w') as f:
        json.dump(files_info, f, indent=4)
    
    print(f"File list saved to {output_file_path}")

# Thay thế `folder_id` bằng ID của thư mục chứa các tệp của bạn
folder_id = '14aa9fYPRS0h8wpB_oHEEGerhuFPue8sN'  # ID thư mục gốc
output_file_path = 'E:\\CODE\\AIC_2024\\Fastapi\\app\\data\\file_list.json'

save_file_list_to_json(drive, folder_id, output_file_path)
