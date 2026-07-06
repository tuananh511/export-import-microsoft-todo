# Export/Import Microsoft To Do

Backup và khôi phục dữ liệu Microsoft To Do (list, task, ghi chú, hạn, nhắc nhở, checklist con) thông qua Microsoft Graph API.

## Cài đặt

```bash
pip install msal requests
```

## Export (backup)

```bash
python export_todo.py
```

- Script sẽ in ra một link kèm mã đăng nhập (device code), ví dụ:
  `To sign in, use a web browser to open the page https://microsoft.com/devicelogin and enter the code XXXXXXX`
- Mở link đó, đăng nhập bằng tài khoản Microsoft đang dùng To Do, nhập mã, bấm **Accept** khi được hỏi quyền truy cập Tasks.
- Sau khi đăng nhập, script tự lấy toàn bộ list và task, lưu ra file `todo_backup_YYYYMMDD_HHMMSS.json` trong thư mục hiện tại.

Nên chạy export định kỳ để có nhiều bản backup theo thời gian (mỗi lần chạy tạo 1 file mới, không đè lên file cũ).

## Import (khôi phục)

```bash
python import_todo.py todo_backup_20260706_101500.json
```

- Đăng nhập tương tự như export.
- Với mỗi list trong file backup:
  - Nếu list đó **đã tồn tại** (trùng tên) trong tài khoản đang đăng nhập → thêm task vào list đó.
  - Nếu **chưa có** → tạo list mới rồi thêm task vào.
- Mỗi task được tạo lại là task **mới** (Microsoft không cho giữ nguyên ID cũ).

⚠️ **Lưu ý:** Chạy import nhiều lần trên cùng 1 file backup + cùng 1 list sẽ tạo task **trùng lặp** (không tự phát hiện task đã tồn tại). Chỉ nên import khi list đó đang trống hoặc khi bạn thực sự muốn khôi phục lại từ đầu.

## Xác thực

Hai script dùng **client ID public của Microsoft** ("Microsoft Graph Command Line Tools"), không cần tự đăng ký app trên Azure. Không có secret hay token nào được lưu lại trên máy — mỗi lần chạy đều cần đăng nhập lại qua trình duyệt.

## Bảo mật khi đưa lên GitHub

File `.gitignore` đã loại trừ các file `todo_backup_*.json` để tránh lỡ commit dữ liệu task cá nhân của bạn. Không có API key hay secret nào trong code, an toàn để public repo.
