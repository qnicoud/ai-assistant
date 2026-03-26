"""SharePoint connector using MSAL device-code auth and Microsoft Graph REST API."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from ai_assistant.docs.config import DocsConfig
from ai_assistant.docs.parsers import SUPPORTED_EXTENSIONS

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_SCOPES = ["Files.Read.All", "Sites.Read.All"]


class SharePointError(Exception):
    """Raised when SharePoint auth or API calls fail."""


class SharePointConnector:
    """Read-only access to a SharePoint document library via Microsoft Graph.

    Authentication uses MSAL device-code flow:
    1. On first use the user is shown a URL + code to authenticate in a browser.
    2. The token is cached locally so subsequent calls are silent.

    Prerequisites (Azure AD app registration):
    - Application type: Public client / native
    - Allow public client flows: Yes
    - API permissions: Files.Read.All, Sites.Read.All (delegated)
    - Set SHAREPOINT_CLIENT_ID and SHAREPOINT_TENANT_ID in config or env.
    """

    def __init__(self, config: DocsConfig) -> None:
        self._config = config
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token

        try:
            import msal  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "msal is required for SharePoint: uv pip install 'ai-assistant[graph]'"
            )

        if not self._config.sharepoint_client_id:
            raise SharePointError(
                "sharepoint_client_id is not configured.\n"
                "Set SHAREPOINT_CLIENT_ID in .env or config.yaml."
            )
        if not self._config.sharepoint_tenant_id:
            raise SharePointError(
                "sharepoint_tenant_id is not configured.\n"
                "Set SHAREPOINT_TENANT_ID in .env or config.yaml."
            )

        cache = msal.SerializableTokenCache()
        cache_path = Path(self._config.sharepoint_token_cache)
        if cache_path.exists():
            cache.deserialize(cache_path.read_text())

        app = msal.PublicClientApplication(
            client_id=self._config.sharepoint_client_id,
            authority=f"https://login.microsoftonline.com/{self._config.sharepoint_tenant_id}",
            token_cache=cache,
        )

        accounts = app.get_accounts()
        result = None
        if accounts:
            result = app.acquire_token_silent(_SCOPES, account=accounts[0])

        if not result:
            flow = app.initiate_device_flow(scopes=_SCOPES)
            if "user_code" not in flow:
                raise SharePointError(f"Failed to initiate device flow: {flow}")
            print(flow["message"])  # instructs user to visit URL + enter code
            result = app.acquire_token_by_device_flow(flow)

        if "access_token" not in result:
            raise SharePointError(
                f"Authentication failed: {result.get('error_description', result)}"
            )

        # Persist token cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(cache.serialize())

        self._token = result["access_token"]
        return self._token

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=_GRAPH_BASE,
            headers={"Authorization": f"Bearer {self._get_token()}"},
            timeout=30.0,
        )

    def _drive_url(self) -> str:
        if self._config.sharepoint_drive_id:
            return f"/drives/{self._config.sharepoint_drive_id}"
        if self._config.sharepoint_site_id:
            return f"/sites/{self._config.sharepoint_site_id}/drive"
        raise SharePointError(
            "Either sharepoint_site_id or sharepoint_drive_id must be configured."
        )

    def list_files(self, folder: str = "/") -> list[dict]:
        """List files in a SharePoint folder. Returns Graph API item dicts."""
        with self._client() as client:
            drive = self._drive_url()
            if folder in ("", "/"):
                url = f"{drive}/root/children"
            else:
                folder_encoded = folder.strip("/")
                url = f"{drive}/root:/{folder_encoded}:/children"

            response = client.get(url, params={"$top": 999})
            if response.status_code != 200:
                raise SharePointError(
                    f"Graph API error {response.status_code}: {response.text}"
                )
            data = response.json()
            return data.get("value", [])

    def download_file(self, item_id: str, dest: Path) -> Path:
        """Download a file by its Graph item ID to dest directory."""
        with self._client() as client:
            drive = self._drive_url()
            # Get download URL
            meta_resp = client.get(f"{drive}/items/{item_id}")
            meta_resp.raise_for_status()
            meta = meta_resp.json()

            filename = meta["name"]
            download_url = meta.get("@microsoft.graph.downloadUrl")
            if not download_url:
                raise SharePointError(f"No download URL for item {item_id}")

            dest.mkdir(parents=True, exist_ok=True)
            file_path = dest / filename

            with client.stream("GET", download_url) as r:
                r.raise_for_status()
                with file_path.open("wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)

        return file_path

    def sync_folder(self, folder: str, dest: Path) -> list[Path]:
        """Download all supported files from a SharePoint folder.

        Skips files that already exist locally with the same eTag (unchanged).
        Returns list of downloaded file paths.
        """
        items = self.list_files(folder)
        dest.mkdir(parents=True, exist_ok=True)

        etag_cache_path = dest / ".etag_cache.json"
        etag_cache: dict[str, str] = {}
        if etag_cache_path.exists():
            etag_cache = json.loads(etag_cache_path.read_text())

        downloaded: list[Path] = []
        for item in items:
            # Skip folders (recurse not implemented in v1)
            if "folder" in item:
                continue

            name: str = item.get("name", "")
            suffix = Path(name).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                continue

            item_id: str = item["id"]
            etag: str = item.get("eTag", "")
            file_path = dest / name

            if file_path.exists() and etag_cache.get(item_id) == etag:
                continue  # unchanged

            try:
                self.download_file(item_id, dest)
                etag_cache[item_id] = etag
                downloaded.append(file_path)
            except SharePointError as e:
                print(f"Warning: failed to download {name}: {e}")

        etag_cache_path.write_text(json.dumps(etag_cache, indent=2))
        return downloaded
