"""
Export toàn bộ Microsoft To Do (list + task + checklist con) ra 1 file JSON.

Cài thư viện cần thiết (1 lần):
    pip install msal requests

Chạy:
    python export_todo.py

KHÔNG cần đăng ký app trên Azure. Script này dùng client ID có sẵn do
Microsoft public ("Microsoft Graph Command Line Tools") dành riêng cho
việc viết script cá nhân qua Graph API.
"""

import json
import time
import requests
import msal

# Client ID chính thức của Microsoft, dùng chung cho mọi người, không cần tự đăng ký app.
CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"

# "common" cho phép đăng nhập cả tài khoản cá nhân (outlook.com, hotmail...)
# và tài khoản công ty/trường học.
AUTHORITY = "https://login.microsoftonline.com/common"

SCOPES = ["Tasks.ReadWrite", "Tasks.ReadWrite.Shared"]
GRAPH = "https://graph.microsoft.com/v1.0"


def get_token():
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise Exception("Không tạo được device flow: " + str(flow))
        print(flow["message"])  # sẽ hiện link + mã để bạn đăng nhập trên trình duyệt
        result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise Exception("Đăng nhập thất bại: " + result.get("error_description", ""))
    return result["access_token"]


def graph_get_all(url, token, params=None):
    """Gọi API và tự động lấy hết các trang (pagination)."""
    items = []
    headers = {"Authorization": f"Bearer {token}"}
    while url:
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
        params = None  # nextLink đã chứa params rồi
    return items


def export_all(token):
    lists = graph_get_all(f"{GRAPH}/me/todo/lists", token)
    backup = {"exportedAt": time.strftime("%Y-%m-%d %H:%M:%S"), "lists": []}

    for lst in lists:
        list_id = lst["id"]
        tasks = graph_get_all(
            f"{GRAPH}/me/todo/lists/{list_id}/tasks",
            token,
            params={"$expand": "checklistItems"},
        )
        backup["lists"].append(
            {
                "displayName": lst.get("displayName"),
                "wellknownListName": lst.get("wellknownListName"),
                "tasks": tasks,
            }
        )
        print(f"  Đã lấy list '{lst.get('displayName')}': {len(tasks)} task")

    return backup


def main():
    print("Đang đăng nhập Microsoft...")
    token = get_token()
    print("Đăng nhập OK. Đang lấy dữ liệu To Do...")
    backup = export_all(token)

    filename = f"todo_backup_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)

    total_tasks = sum(len(l["tasks"]) for l in backup["lists"])
    print(f"\nHoàn tất: {len(backup['lists'])} list, {total_tasks} task")
    print(f"File backup: {filename}")


if __name__ == "__main__":
    main()
