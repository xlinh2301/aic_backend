import os
import json
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# Đảm bảo rằng đường dẫn đến tệp client_secrets.json là chính xác
client_secrets_path = 'E:\\AIC\\aic_backend\\app\\data\\client_secrets.json'

# Cấu hình PyDrive và xác thực
gauth = GoogleAuth()
gauth.LoadClientConfigFile(client_secrets_path)
gauth.LocalWebserverAuth()  # Cho phép xác thực qua trình duyệt web

# Tạo đối tượng GoogleDrive
drive = GoogleDrive(gauth)

def get_image_ids(drive, folder_id):
    """Lấy ID và tên của các ảnh (JPEG, PNG) trong thư mục và các thư mục con"""
    image_info_list = []
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
                
                if mime_type == 'application/vnd.google-apps.folder':
                    # Nếu là thư mục, thêm vào danh sách để xử lý tiếp
                    folders.append(file_id)
                    print(f"Thêm thư mục con: {file_title}, ID: {file_id}")
                elif mime_type in ['image/jpeg', 'image/png', 'image/jpg']:
                    # Chỉ thêm các ảnh có định dạng JPEG hoặc PNG
                    image_info = {
                        'id': file_id,
                        'title': file_title
                    }
                    image_info_list.append(image_info)
                    print(f"Thêm ảnh: {file_title}, ID: {file_id}")
                else:
                    print(f"Bỏ qua tệp: {file_title} (mimeType: {mime_type})")
            
            # Lấy pageToken cho trang tiếp theo nếu có
            page_token = drive.auth.service.files().list(q=query, pageToken=page_token).execute().get('nextPageToken')
            if not page_token:
                break
    
    return image_info_list

# Thay thế `folder_id` bằng ID của thư mục chứa các tệp ảnh của bạn
folder_id = '1pi5sKtD_PTEijpyUD49oX_NGrB5cc59u'  # ID thư mục gốc
image_info_list = get_image_ids(drive, folder_id)

# Lưu thông tin ảnh vào file JSON mới
output_file_path = 'E:\\AIC\\aic_backend\\app\\file_image_list.json'
with open(output_file_path, 'w') as f:
    json.dump(image_info_list, f, indent=4)

print(f"File JSON mới đã được lưu tại {output_file_path}")
