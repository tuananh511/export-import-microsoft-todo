"""
todo_core.py - logic dùng chung cho GUI (todo_gui.py).

Giữ nguyên cách làm của export_todo.py / import_todo.py:
- Device code flow với client ID public của Microsoft, không cần đăng ký app Azure.
- Không ghi token ra đĩa. Token chỉ nằm trong RAM của phiên đang mở,
  nên export xong import ngay không phải đăng nhập lại, đóng app là mất.

Khác biệt nhỏ so với bản CLI:
- Có callback (log / progress / device code) để GUI hiển thị.
- Có thể huỷ giữa chừng.
- Tự chờ rồi thử lại khi Graph báo 429/503 (import nhiều task dễ dính).
"""

import time

import msal
import requests

CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["Tasks.ReadWrite", "Tasks.ReadWrite.Shared"]
GRAPH = "https://graph.microsoft.com/v1.0"


class Cancelled(Exception):
    pass


class TodoSession:
    def __init__(self):
        # Tạo muộn (lúc bấm nút) vì msal gọi mạng ngay khi khởi tạo: nếu mất mạng
        # thì cửa sổ vẫn mở được và lỗi hiện thân thiện thay vì sập lúc khởi động.
        # Token cache mặc định của msal nằm trong RAM, không ghi file.
        self._app_instance = None

        # GUI gán lại các callback này trước mỗi lần chạy.
        self.log = print
        self.on_progress = lambda done, total: None
        self.on_device_code = lambda code, uri, message: print(message)
        self.on_logged_in = lambda: None
        self.is_cancelled = lambda: False

    @property
    def _app(self):
        if self._app_instance is None:
            self._app_instance = msal.PublicClientApplication(
                CLIENT_ID, authority=AUTHORITY
            )
        return self._app_instance

    # ---------- tiện ích ----------
    def _check(self):
        if self.is_cancelled():
            raise Cancelled()

    def _sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self._check()
            time.sleep(0.2)

    # ---------- đăng nhập ----------
    def token(self):
        accounts = self._app.get_accounts()
        result = None
        if accounts:
            result = self._app.acquire_token_silent(SCOPES, account=accounts[0])

        if not result:
            flow = self._app.initiate_device_flow(scopes=SCOPES)
            if "user_code" not in flow:
                raise RuntimeError("Không tạo được device flow: " + str(flow))
            self.on_device_code(
                flow["user_code"],
                flow.get("verification_uri", "https://microsoft.com/devicelogin"),
                flow.get("message", ""),
            )
            result = self._app.acquire_token_by_device_flow(
                flow, exit_condition=lambda f: self.is_cancelled()
            )
            self._check()
            if result and "access_token" in result:
                self.on_logged_in()

        if not result or "access_token" not in result:
            desc = (result or {}).get("error_description", "")
            raise RuntimeError("Đăng nhập thất bại: " + desc)
        return result["access_token"]

    # ---------- gọi Graph ----------
    def _req(self, method, url, **kwargs):
        resp = None
        for attempt in range(5):
            self._check()
            headers = {"Authorization": f"Bearer {self.token()}"}
            resp = requests.request(method, url, headers=headers, timeout=60, **kwargs)
            if resp.status_code in (429, 503, 504):
                try:
                    wait = int(resp.headers.get("Retry-After", 2 ** attempt))
                except ValueError:
                    wait = 2 ** attempt
                self.log(f"  Graph đang giới hạn tốc độ, chờ {wait}s rồi thử lại...")
                self._sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        resp.raise_for_status()
        return resp

    def _get_all(self, url, params=None):
        """Gọi API và tự lấy hết các trang (pagination)."""
        items = []
        while url:
            data = self._req("GET", url, params=params).json()
            items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            params = None  # nextLink đã chứa params
        return items

    # ---------- export ----------
    def export_all(self):
        self.log("Đang đăng nhập Microsoft...")
        lists = self._get_all(f"{GRAPH}/me/todo/lists")
        self.log(f"Đăng nhập OK. Tìm thấy {len(lists)} list.")

        backup = {"exportedAt": time.strftime("%Y-%m-%d %H:%M:%S"), "lists": []}
        for i, lst in enumerate(lists, start=1):
            self._check()
            tasks = self._get_all(
                f"{GRAPH}/me/todo/lists/{lst['id']}/tasks",
                params={"$expand": "checklistItems"},
            )
            backup["lists"].append(
                {
                    "displayName": lst.get("displayName"),
                    "wellknownListName": lst.get("wellknownListName"),
                    "tasks": tasks,
                }
            )
            self.log(f"  Đã lấy list '{lst.get('displayName')}': {len(tasks)} task")
            self.on_progress(i, len(lists))
        return backup

    # ---------- import ----------
    def _existing_lists(self):
        lists = self._get_all(f"{GRAPH}/me/todo/lists")
        return {l["displayName"]: l["id"] for l in lists}

    def _create_list(self, name):
        resp = self._req("POST", f"{GRAPH}/me/todo/lists", json={"displayName": name})
        return resp.json()["id"]

    def _create_task(self, list_id, task):
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

        new_task = self._req(
            "POST", f"{GRAPH}/me/todo/lists/{list_id}/tasks", json=payload
        ).json()

        for item in task.get("checklistItems", []):
            try:
                self._req(
                    "POST",
                    f"{GRAPH}/me/todo/lists/{list_id}/tasks/{new_task['id']}/checklistItems",
                    json={
                        "displayName": item.get("displayName"),
                        "isChecked": item.get("isChecked", False),
                    },
                )
            except requests.HTTPError as e:
                self.log(f"  Cảnh báo: lỗi thêm checklist '{item.get('displayName')}': {e}")

    def import_backup(self, backup):
        total = sum(len(l.get("tasks", [])) for l in backup["lists"])
        done = 0

        self.log("Đang đăng nhập Microsoft...")
        existing = self._existing_lists()
        self.log("Đăng nhập OK. Bắt đầu import.")

        for lst in backup["lists"]:
            self._check()
            name = lst["displayName"]
            if name in existing:
                list_id = existing[name]
                self.log(f"List '{name}' đã tồn tại -> thêm task vào list này.")
            else:
                list_id = self._create_list(name)
                existing[name] = list_id
                self.log(f"Đã tạo list mới '{name}'.")

            for task in lst.get("tasks", []):
                self._check()
                self._create_task(list_id, task)
                done += 1
                self.on_progress(done, total)
            self.log(f"  -> Import xong {len(lst.get('tasks', []))} task vào '{name}'")

        return len(backup["lists"]), total
