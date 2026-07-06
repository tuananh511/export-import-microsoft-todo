"""
Import lại Microsoft To Do từ file JSON đã export bằng export_todo.py

Cài thư viện cần thiết (1 lần):
    pip install msal requests

Chạy:
    python import_todo.py todo_backup_20260706_101500.json

KHÔNG cần đăng ký app trên Azure. Script này dùng client ID có sẵn do
Microsoft public ("Microsoft Graph Command Line Tools") dành riêng cho
việc viết script cá nhân qua Graph API.
"""

import json
import sys
import requests
import msal

# Client ID chính thức của Microsoft, dùng chung cho mọi người, không cần tự đăng ký app.
CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"

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
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
    if "access_token" not in result:
        raise Exception("Đăng nhập thất bại: " + result.get("error_description", ""))
    return result["access_token"]


def get_existing_lists(token):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{GRAPH}/me/todo/lists", headers=headers)
    resp.raise_for_status()
    return {l["displayName"]: l["id"] for l in resp.json().get("value", [])}


def create_list(token, name):
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{GRAPH}/me/todo/lists", headers=headers, json={"displayName": name})
    resp.raise_for_status()
    return resp.json()["id"]


def create_task(token, list_id, task):
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": task.get("title"),
        "importance": task.get("importance", "normal"),
        "status": task.get("status", "notStarted"),
    }
    if task.get("body") and task["body"].get("content"):
        payload["body"] = task["body"]
    if task.get("dueDateTime"):
        payload["dueDateTime"] = task["dueDateTime"]
    if task.get("reminderDateTime"):
        payload["reminderDateTime"] = task["reminderDateTime"]
        payload["isReminderOn"] = True

    resp = requests.post(f"{GRAPH}/me/todo/lists/{list_id}/tasks", headers=headers, json=payload)
    resp.raise_for_status()
    new_task = resp.json()

    for item in task.get("checklistItems", []):
        requests.post(
            f"{GRAPH}/me/todo/lists/{list_id}/tasks/{new_task['id']}/checklistItems",
            headers=headers,
            json={
                "displayName": item.get("displayName"),
                "isChecked": item.get("isChecked", False),
            },
        )
    return new_task


def main():
    if len(sys.argv) < 2:
        print("Cách dùng: python import_todo.py <file_backup.json>")
        return

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        backup = json.load(f)

    print("Đang đăng nhập Microsoft...")
    token = get_token()
    existing = get_existing_lists(token)

    for lst in backup["lists"]:
        name = lst["displayName"]
        if name in existing:
            list_id = existing[name]
            print(f"List '{name}' đã tồn tại -> thêm task vào list này.")
        else:
            list_id = create_list(token, name)
            print(f"Đã tạo list mới '{name}'.")

        for task in lst["tasks"]:
            create_task(token, list_id, task)

        print(f"  -> Import xong {len(lst['tasks'])} task vào '{name}'")

    print("\nHoàn tất!")


if __name__ == "__main__":
    main()
