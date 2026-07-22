# Export/Import Microsoft To Do
> Sao lưu và khôi phục toàn bộ dữ liệu Microsoft To Do qua Microsoft Graph API.

![Release](https://img.shields.io/github/v/release/tuananh511/export-import-microsoft-todo?include_prereleases)
![License](https://img.shields.io/github/license/tuananh511/export-import-microsoft-todo)
![Build](https://img.shields.io/badge/build-passing-brightgreen)

## Overview
Hai script Python độc lập giúp bạn sao lưu (export) và khôi phục (import) dữ liệu Microsoft To Do — bao gồm list, task, ghi chú, hạn, nhắc nhở và checklist con — thông qua Microsoft Graph API. Không cần tự đăng ký app trên Azure, không lưu secret hay token nào trên máy.

## Features
- Xuất toàn bộ list và task ra file JSON có gắn timestamp (`todo_backup_YYYYMMDD_HHMMSS.json`)
- Nhập lại dữ liệu từ file backup: tự động thêm vào list đã tồn tại (trùng tên) hoặc tạo list mới nếu chưa có
- Đăng nhập qua device code flow bằng client ID public của Microsoft ("Microsoft Graph Command Line Tools"), không cần đăng ký app Azure riêng
- Không lưu secret/token trên máy — mỗi lần chạy đều yêu cầu đăng nhập lại qua trình duyệt
- `.gitignore` sẵn loại trừ file `todo_backup_*.json` để tránh lỡ commit dữ liệu cá nhân

## Installation
```
git clone https://github.com/tuananh511/export-import-microsoft-todo.git
cd export-import-microsoft-todo
pip install msal requests
```

## Usage
**Export (backup):**
```
python export_todo.py
```
- Script in ra một link kèm device code, ví dụ: `https://microsoft.com/devicelogin` + mã.
- Mở link, đăng nhập bằng tài khoản Microsoft đang dùng To Do, nhập mã, chấp nhận quyền truy cập Tasks.
- Toàn bộ list và task được lưu ra file `todo_backup_YYYYMMDD_HHMMSS.json` trong thư mục hiện tại.
- Nên chạy export định kỳ để có nhiều bản backup theo thời gian (mỗi lần chạy tạo file mới, không đè file cũ).

**Import (khôi phục):**
```
python import_todo.py todo_backup_20260706_101500.json
```
- Đăng nhập tương tự như export.
- Với mỗi list trong file backup: nếu đã tồn tại (trùng tên) → thêm task vào list đó; nếu chưa có → tạo list mới rồi thêm task.

⚠️ **Lưu ý:** Import nhiều lần trên cùng 1 file + cùng 1 list sẽ tạo task **trùng lặp** (script không tự phát hiện task đã tồn tại). Chỉ nên import khi list đang trống hoặc khi thực sự muốn khôi phục lại từ đầu.

## Roadmap
- [ ] Phát hiện và bỏ qua task trùng lặp khi import
- [ ] Đóng gói thành file thực thi (.exe) hoặc CLI có thể cài qua pip
- [ ] Thêm CI (GitHub Actions) để kiểm tra script tự động

## License
MIT
