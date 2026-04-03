from __future__ import annotations

import json
import mimetypes
import os
import sys
import tempfile
import time
from collections.abc import Callable


class FeishuApiClient:
    def __init__(
        self,
        *,
        config_getter: Callable[[], dict],
        requests_module,
    ) -> None:
        self._config_getter = config_getter
        self._requests = requests_module
        self._token_cache = {"token": None, "expire": 0.0}
        self._config_signature = ""

    @staticmethod
    def build_config_signature(config: dict | None) -> str:
        cfg = dict(config or {})
        app_id = str(cfg.get("app_id") or "").strip()
        app_secret = str(cfg.get("app_secret") or "").strip()
        return f"{app_id}::{app_secret}"

    @staticmethod
    def validate_runtime_config(config: dict | None) -> list[str]:
        cfg = dict(config or {})
        missing: list[str] = []
        for key in ("app_id", "app_secret"):
            if not str(cfg.get(key) or "").strip():
                missing.append(key)
        return missing

    def sync_runtime_config(self, config: dict | None) -> None:
        signature = self.build_config_signature(config)
        if signature != self._config_signature:
            self.clear_token_cache()
            self._config_signature = signature

    def run_preflight(self, *, auth_probe: bool = False) -> dict[str, object]:
        config = dict(self._config_getter() or {})
        self.sync_runtime_config(config)
        missing = self.validate_runtime_config(config)
        result: dict[str, object] = {
            "ok": not missing,
            "missing": missing,
            "workspace_root": str(config.get("workspace_root") or "").strip(),
            "app_id_preview": str(config.get("app_id") or "").strip()[:12],
            "auth_probe": auth_probe,
        }
        if missing:
            result["error"] = f"missing config keys: {', '.join(missing)}"
            return result
        if auth_probe:
            try:
                token = self.get_tenant_access_token()
                result["token_preview"] = f"{token[:12]}..." if token else ""
            except Exception as exc:
                result["ok"] = False
                result["error"] = str(exc)
        return result

    def get_tenant_access_token(self) -> str:
        cfg = self._config_getter() or {}
        self.sync_runtime_config(cfg)
        missing = self.validate_runtime_config(cfg)
        if missing:
            raise RuntimeError(f"缺少飞书配置: {', '.join(missing)}")
        if self._token_cache["token"] and time.time() < float(self._token_cache["expire"] or 0.0) - 60:
            return str(self._token_cache["token"])
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = self._requests.post(url, json={"app_id": cfg["app_id"], "app_secret": cfg["app_secret"]})
        data = resp.json()
        if data.get("code") == 0:
            self._token_cache["token"] = data["tenant_access_token"]
            self._token_cache["expire"] = time.time() + float(data.get("expire", 7200) or 7200)
            return str(self._token_cache["token"])
        raise RuntimeError(f"获取 token 失败: {data}")

    def download_message_images(self, message_id: str, image_keys: list[str]) -> list[str]:
        if not image_keys:
            return []
        token = self.get_tenant_access_token()
        base_url = "https://open.feishu.cn/open-apis/im/v1/messages"
        paths = []
        tmp_dir = os.path.join(tempfile.gettempdir(), "feishu-bot-images")
        os.makedirs(tmp_dir, exist_ok=True)
        for i, key in enumerate(image_keys):
            try:
                url = f"{base_url}/{message_id}/resources/{key}?type=image"
                resp = self._requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
                if resp.status_code != 200:
                    continue
                ext = _content_type_to_ext(resp.headers.get("Content-Type", ""))
                path = os.path.join(tmp_dir, f"{message_id.replace('/', '_')}_{i}.{ext}")
                with open(path, "wb") as f:
                    f.write(resp.content)
                paths.append(os.path.abspath(path))
            except Exception as exc:
                print(f"[下载图片失败] {key}: {exc}", file=sys.stderr)
        return paths

    def fetch_remote_image_to_temp(self, image_url: str) -> str | None:
        try:
            resp = self._requests.get(image_url, timeout=20)
            if resp.status_code != 200:
                return None
            ext = _content_type_to_ext(resp.headers.get("Content-Type", ""))
            tmp_dir = os.path.join(tempfile.gettempdir(), "feishu-bot-images")
            os.makedirs(tmp_dir, exist_ok=True)
            path = os.path.join(tmp_dir, f"reply_{int(time.time() * 1000)}.{ext}")
            with open(path, "wb") as f:
                f.write(resp.content)
            return os.path.abspath(path)
        except Exception:
            return None

    def upload_image(self, file_path: str) -> str | None:
        try:
            if not file_path or not os.path.isfile(file_path):
                return None
            token = self.get_tenant_access_token()
            url = "https://open.feishu.cn/open-apis/im/v1/images"
            mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            with open(file_path, "rb") as f:
                files = {"image": (os.path.basename(file_path), f, mime)}
                data = {"image_type": "message"}
                headers = {"Authorization": f"Bearer {token}"}
                resp = self._requests.post(url, headers=headers, data=data, files=files, timeout=30)
            payload = resp.json()
            if payload.get("code") == 0:
                return (payload.get("data") or {}).get("image_key")
        except Exception as exc:
            print(f"上传图片失败: {exc}", file=sys.stderr)
        return None

    def upload_file(self, file_path: str) -> str | None:
        try:
            if not file_path or not os.path.isfile(file_path):
                print(f"[上传文件] 无效路径或非文件: {file_path}", flush=True)
                return None
            size = os.path.getsize(file_path)
            if size == 0:
                print(f"[上传文件] 空文件跳过: {file_path}", flush=True)
                return None
            token = self.get_tenant_access_token()
            url = "https://open.feishu.cn/open-apis/im/v1/files"
            fname = os.path.basename(file_path)
            ext = (os.path.splitext(fname)[1] or "").lstrip(".").lower() or "bin"
            file_type = "stream" if ext in ("md", "txt", "json", "csv", "yaml", "yml", "xml", "html") else ext
            mime = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            with open(file_path, "rb") as f:
                files = {"file": (fname, f, mime)}
                data = {"file_type": file_type, "file_name": fname}
                headers = {"Authorization": f"Bearer {token}"}
                resp = self._requests.post(url, headers=headers, data=data, files=files, timeout=60)
            payload = resp.json()
            if payload.get("code") == 0:
                file_key = (payload.get("data") or {}).get("file_key")
                preview = (file_key[:40] + "...") if file_key and len(file_key) > 40 else (file_key or "None")
                print(f"[上传文件] 成功: {fname} -> file_key={preview}", flush=True)
                return file_key
            print(f"[上传文件] 失败 code={payload.get('code')} msg={payload.get('msg')}: {file_path}", flush=True)
        except Exception as exc:
            print(f"[上传文件] 异常: {exc} | {file_path}", flush=True)
        return None

    def reply_image(self, message_id: str, image_key: str) -> bool:
        try:
            return self._post_reply_message(message_id, "image", {"image_key": image_key})
        except Exception as exc:
            print(f"回复图片异常: {exc}", file=sys.stderr)
            return False

    def reply_file(self, message_id: str, file_key: str) -> bool:
        try:
            ok, data = self._post_reply_message_with_payload(message_id, "file", {"file_key": file_key})
            if not ok:
                print(f"[回复文件] 失败 code={data.get('code')} msg={data.get('msg')}", flush=True)
            else:
                print("[回复文件] 成功", flush=True)
            return ok
        except Exception as exc:
            print(f"[回复文件] 异常: {exc}", flush=True)
            return False

    def reply_raw_message(self, message_id: str, msg_type: str, content_payload: dict, *, timeout: int = 15) -> tuple[bool, dict]:
        return self._post_reply_message_with_payload(message_id, msg_type, content_payload, timeout=timeout)

    def update_raw_message(self, message_id: str, msg_type: str, content_payload: dict, *, timeout: int = 15) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {"content": json.dumps(content_payload, ensure_ascii=False), "msg_type": msg_type}
        patch = getattr(self._requests, "patch", None)
        if callable(patch):
            resp = patch(url, headers=headers, json=body, timeout=timeout)
        else:
            request = getattr(self._requests, "request", None)
            if not callable(request):
                raise RuntimeError("requests module does not support PATCH updates")
            resp = request("PATCH", url, headers=headers, json=body, timeout=timeout)
        data = resp.json()
        return data.get("code") == 0, data

    def send_raw_message(self, receive_id: str, receive_id_type: str, msg_type: str, content_payload: dict, *, timeout: int = 15) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content_payload, ensure_ascii=False),
        }
        resp = self._requests.post(url, headers=headers, json=body, timeout=timeout)
        data = resp.json()
        return data.get("code") == 0, data

    def get_message(self, message_id: str, *, timeout: int = 15) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
        headers = {"Authorization": f"Bearer {token}"}
        resp = self._requests.get(url, headers=headers, timeout=timeout)
        data = resp.json()
        return data.get("code") == 0, data

    def list_messages(
        self,
        *,
        container_id: str,
        container_id_type: str = "chat",
        page_size: int = 20,
        sort_type: str = "ByCreateTimeDesc",
        page_token: str | None = None,
        timeout: int = 15,
    ) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "container_id_type": container_id_type,
            "container_id": container_id,
            "page_size": max(1, min(int(page_size or 20), 50)),
            "sort_type": sort_type,
        }
        if page_token:
            params["page_token"] = page_token
        resp = self._requests.get(url, headers=headers, params=params, timeout=timeout)
        data = resp.json()
        return data.get("code") == 0, data

    def create_docx_document(self, title: str, *, folder_token: str = "", timeout: int = 15) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        url = "https://open.feishu.cn/open-apis/docx/v1/documents"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {"title": str(title or "").strip() or "Task Doc"}
        folder = str(folder_token or "").strip()
        if folder:
            body["folder_token"] = folder
        resp = self._requests.post(url, headers=headers, json=body, timeout=timeout)
        data = resp.json()
        return data.get("code") == 0, data

    def convert_docx_markdown(self, content: str, *, timeout: int = 15) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        url = "https://open.feishu.cn/open-apis/docx/v1/documents/blocks/convert"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {"content_type": "markdown", "content": str(content or "")}
        resp = self._requests.post(url, headers=headers, json=body, timeout=timeout)
        data = resp.json()
        return data.get("code") == 0, data

    def get_docx_block_children(
        self,
        document_id: str,
        *,
        block_id: str = "",
        page_token: str = "",
        page_size: int = 200,
        timeout: int = 15,
    ) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        target_document_id = str(document_id or "").strip()
        target_block_id = str(block_id or target_document_id).strip() or target_document_id
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{target_document_id}/blocks/{target_block_id}/children"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"page_size": max(1, min(int(page_size or 200), 500))}
        if page_token:
            params["page_token"] = str(page_token)
        resp = self._requests.get(url, headers=headers, params=params, timeout=timeout)
        data = resp.json()
        return data.get("code") == 0, data

    def batch_delete_docx_block_children(
        self,
        document_id: str,
        *,
        block_id: str = "",
        start_index: int = 0,
        end_index: int = 0,
        timeout: int = 15,
    ) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        target_document_id = str(document_id or "").strip()
        target_block_id = str(block_id or target_document_id).strip() or target_document_id
        url = (
            "https://open.feishu.cn/open-apis/docx/v1/documents/"
            f"{target_document_id}/blocks/{target_block_id}/children/batch_delete"
        )
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        request = getattr(self._requests, "request", None)
        if not callable(request):
            raise RuntimeError("requests module does not support generic request() for DELETE docx updates")
        resp = request(
            "DELETE",
            url,
            headers=headers,
            json={"start_index": int(start_index or 0), "end_index": int(end_index or 0)},
            timeout=timeout,
        )
        data = resp.json()
        return data.get("code") == 0, data

    def create_docx_block_children(
        self,
        document_id: str,
        children: list[dict],
        *,
        block_id: str = "",
        index: int = -1,
        timeout: int = 15,
    ) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        target_document_id = str(document_id or "").strip()
        target_block_id = str(block_id or target_document_id).strip() or target_document_id
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{target_document_id}/blocks/{target_block_id}/children"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = self._requests.post(
            url,
            headers=headers,
            json={"children": list(children or []), "index": int(index)},
            timeout=timeout,
        )
        data = resp.json()
        return data.get("code") == 0, data

    def send_file_by_open_id(self, open_id: str, file_key: str, receive_id_type: str = "open_id") -> bool:
        try:
            ok, data = self.send_raw_message(open_id, receive_id_type, "file", {"file_key": file_key})
            if not ok:
                print(f"[open_id发送文件] 失败 code={data.get('code')} msg={data.get('msg')}", flush=True)
            else:
                print(f"[open_id发送文件] 成功 open_id={open_id[:20]}...", flush=True)
            return ok
        except Exception as exc:
            print(f"[open_id发送文件] 异常: {exc}", flush=True)
            return False

    def send_image_by_open_id(self, open_id: str, image_key: str, receive_id_type: str = "open_id") -> bool:
        try:
            ok, data = self.send_raw_message(open_id, receive_id_type, "image", {"image_key": image_key})
            if not ok:
                print(f"[open_id发送图片] 失败 code={data.get('code')} msg={data.get('msg')}", flush=True)
            else:
                print(f"[open_id发送图片] 成功 open_id={open_id[:20]}...", flush=True)
            return ok
        except Exception as exc:
            print(f"[open_id发送图片] 异常: {exc}", flush=True)
            return False

    def clear_token_cache(self) -> None:
        self._token_cache = {"token": None, "expire": 0.0}

    def _post_reply_message(self, message_id: str, msg_type: str, content_payload: dict, *, timeout: int = 15) -> bool:
        ok, _ = self._post_reply_message_with_payload(message_id, msg_type, content_payload, timeout=timeout)
        return ok

    def _post_reply_message_with_payload(self, message_id: str, msg_type: str, content_payload: dict, *, timeout: int = 15) -> tuple[bool, dict]:
        token = self.get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = {"content": json.dumps(content_payload, ensure_ascii=False), "msg_type": msg_type}
        resp = self._requests.post(url, headers=headers, json=body, timeout=timeout)
        data = resp.json()
        return data.get("code") == 0, data


def _content_type_to_ext(content_type: str) -> str:
    lowered = str(content_type or "").lower()
    if "jpeg" in lowered or "jpg" in lowered:
        return "jpg"
    if "gif" in lowered:
        return "gif"
    if "webp" in lowered:
        return "webp"
    if "bmp" in lowered:
        return "bmp"
    return "png"


__all__ = ["FeishuApiClient"]
