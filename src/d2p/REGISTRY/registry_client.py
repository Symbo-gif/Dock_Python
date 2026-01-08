# Copyright 2024 Michael Maillet, Damien Davison, Sacha Davison
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Docker registry client for pulling images.
Implements the Docker Registry HTTP API V2.
"""

import json
import os
import hashlib
import gzip
import tarfile
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from .image_reference import ImageReference


@dataclass
class RegistryAuth:
    """Authentication credentials for a registry."""

    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None


class RegistryClient:
    """
    Client for interacting with Docker registries.
    Supports Docker Hub and OCI-compatible registries.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the registry client.

        Args:
            cache_dir: Directory to cache downloaded layers. Defaults to ~/.d2p/cache
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".d2p" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._auth_tokens: Dict[str, str] = {}
        self._credentials: Dict[str, RegistryAuth] = {}

    def set_credentials(self, registry: str, username: str, password: str) -> None:
        """
        Set credentials for a registry.

        Args:
            registry: Registry hostname (e.g., 'docker.io')
            username: Username
            password: Password or access token
        """
        self._credentials[registry] = RegistryAuth(username=username, password=password)

    def _get_auth_token(self, ref: ImageReference) -> Optional[str]:
        """Get authentication token for a registry."""
        # Check cached token
        cache_key = f"{ref.registry}/{ref.repository}"
        if cache_key in self._auth_tokens:
            return self._auth_tokens[cache_key]

        # For Docker Hub, get token from auth service
        if ref.registry == "docker.io":
            token = self._get_docker_hub_token(ref)
            if token:
                self._auth_tokens[cache_key] = token
            return token

        # For other registries, try basic auth if credentials exist
        creds = self._credentials.get(ref.registry)
        if creds and creds.username and creds.password:
            import base64

            auth = base64.b64encode(
                f"{creds.username}:{creds.password}".encode()
            ).decode()
            return f"Basic {auth}"

        return None

    def _get_docker_hub_token(self, ref: ImageReference) -> Optional[str]:
        """Get a Docker Hub authentication token."""
        try:
            # Docker Hub uses bearer token auth
            params = {
                "service": "registry.docker.io",
                "scope": f"repository:{ref.repository}:pull",
            }
            url = f"https://auth.docker.io/token?{urlencode(params)}"

            request = Request(url)

            # Add basic auth if credentials are available
            creds = self._credentials.get("docker.io")
            if creds and creds.username and creds.password:
                import base64

                auth = base64.b64encode(
                    f"{creds.username}:{creds.password}".encode()
                ).decode()
                request.add_header("Authorization", f"Basic {auth}")

            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode())
                return f"Bearer {data['token']}"

        except Exception as e:
            print(f"Warning: Failed to get Docker Hub token: {e}")
            return None

    def _make_request(
        self, url: str, ref: ImageReference, accept: Optional[str] = None
    ) -> Tuple[bytes, Dict[str, str]]:
        """Make an authenticated request to the registry."""
        request = Request(url)

        # Add auth token
        token = self._get_auth_token(ref)
        if token:
            request.add_header("Authorization", token)

        # Add accept header
        if accept:
            request.add_header("Accept", accept)

        try:
            with urlopen(request, timeout=60) as response:
                headers = dict(response.headers)
                return response.read(), headers
        except HTTPError as e:
            if e.code == 401:
                # Token might have expired, clear and retry
                cache_key = f"{ref.registry}/{ref.repository}"
                if cache_key in self._auth_tokens:
                    del self._auth_tokens[cache_key]
                    return self._make_request(url, ref, accept)
            raise

    def get_manifest(self, ref: ImageReference) -> Dict[str, Any]:
        """
        Get the image manifest.

        Args:
            ref: Image reference

        Returns:
            Manifest as a dictionary
        """
        tag_or_digest = ref.digest if ref.digest else ref.tag
        url = f"{ref.registry_url}/v2/{ref.repository}/manifests/{tag_or_digest}"

        # Accept multiple manifest types
        accept = ", ".join(
            [
                "application/vnd.docker.distribution.manifest.v2+json",
                "application/vnd.docker.distribution.manifest.list.v2+json",
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.oci.image.index.v1+json",
            ]
        )

        content, headers = self._make_request(url, ref, accept)
        manifest = json.loads(content.decode())

        # Handle manifest list (multi-arch images)
        if manifest.get("mediaType") in [
            "application/vnd.docker.distribution.manifest.list.v2+json",
            "application/vnd.oci.image.index.v1+json",
        ]:
            # Get the manifest for the current platform
            manifest = self._select_platform_manifest(ref, manifest)

        return manifest

    def _select_platform_manifest(
        self, ref: ImageReference, manifest_list: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Select the appropriate manifest for the current platform."""
        import platform

        # Map Python platform to Docker platform
        os_name = platform.system().lower()
        arch = platform.machine().lower()

        arch_map = {
            "x86_64": "amd64",
            "aarch64": "arm64",
            "armv7l": "arm",
            "i386": "386",
            "i686": "386",
        }
        arch = arch_map.get(arch, arch)

        # Find matching manifest
        for manifest in manifest_list.get("manifests", []):
            platform_info = manifest.get("platform", {})
            if (
                platform_info.get("os") == os_name
                and platform_info.get("architecture") == arch
            ):
                # Fetch the actual manifest
                digest = manifest["digest"]
                new_ref = ImageReference(
                    registry=ref.registry, repository=ref.repository, digest=digest
                )
                return self.get_manifest(new_ref)

        # Fall back to first manifest
        if manifest_list.get("manifests"):
            first = manifest_list["manifests"][0]
            new_ref = ImageReference(
                registry=ref.registry, repository=ref.repository, digest=first["digest"]
            )
            return self.get_manifest(new_ref)

        raise ValueError("No suitable manifest found")

    def get_config(
        self, ref: ImageReference, manifest: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get the image configuration.

        Args:
            ref: Image reference
            manifest: Image manifest

        Returns:
            Image configuration as a dictionary
        """
        config = manifest.get("config", {})
        digest = config.get("digest", "")

        if not digest:
            raise ValueError("No config digest in manifest")

        url = f"{ref.registry_url}/v2/{ref.repository}/blobs/{digest}"
        content, _ = self._make_request(url, ref)

        return json.loads(content.decode())

    def pull_layer(
        self, ref: ImageReference, layer: Dict[str, Any], dest_dir: Path
    ) -> Path:
        """
        Pull and extract an image layer.

        Args:
            ref: Image reference
            layer: Layer descriptor from manifest
            dest_dir: Directory to extract layer to

        Returns:
            Path to extracted layer
        """
        digest = layer.get("digest", "")
        if not digest:
            raise ValueError("No digest in layer")

        # Check cache first
        cache_path = self.cache_dir / "layers" / digest.replace(":", "_")
        if cache_path.exists():
            print(f"Using cached layer: {digest[:19]}...")
            return cache_path

        print(f"Pulling layer: {digest[:19]}...")

        # Download layer
        url = f"{ref.registry_url}/v2/{ref.repository}/blobs/{digest}"
        content, _ = self._make_request(url, ref)

        # Verify digest
        actual_digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
        if actual_digest != digest:
            raise ValueError(
                f"Layer digest mismatch: expected {digest}, got {actual_digest}"
            )

        # Save to cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(content)

        return cache_path

    def extract_layer(self, layer_path: Path, dest_dir: Path) -> None:
        """
        Extract a layer tarball to a directory.

        Args:
            layer_path: Path to the layer tarball
            dest_dir: Directory to extract to
        """
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Layers are typically gzipped tarballs
        try:
            with gzip.open(layer_path, "rb") as gz:
                with tarfile.open(fileobj=gz, mode="r:") as tar:
                    # Extract safely, avoiding path traversal
                    for member in tar.getmembers():
                        # Skip absolute paths and parent directory references
                        if member.name.startswith("/") or ".." in member.name:
                            continue
                        # Handle whiteout files (Docker layer deletion markers)
                        if ".wh." in member.name:
                            self._handle_whiteout(dest_dir, member.name)
                            continue
                        tar.extract(member, dest_dir)
        except gzip.BadGzipFile:
            # Try as uncompressed tar
            with tarfile.open(layer_path, mode="r:") as tar:
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in member.name:
                        continue
                    if ".wh." in member.name:
                        self._handle_whiteout(dest_dir, member.name)
                        continue
                    tar.extract(member, dest_dir)

    def _handle_whiteout(self, dest_dir: Path, whiteout_path: str) -> None:
        """Handle Docker whiteout file (marks a file as deleted)."""
        # .wh.filename means delete filename
        # .wh..wh..opq means delete everything in the directory

        parts = whiteout_path.split("/")
        filename = parts[-1]

        if filename == ".wh..wh..opq":
            # Opaque whiteout - delete everything in directory
            dir_path = dest_dir / "/".join(parts[:-1])
            if dir_path.exists() and dir_path.is_dir():
                import shutil

                for item in dir_path.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
        elif filename.startswith(".wh."):
            # Regular whiteout - delete specific file
            real_name = filename[4:]  # Remove .wh. prefix
            file_path = dest_dir / "/".join(parts[:-1]) / real_name
            if file_path.exists():
                if file_path.is_dir():
                    import shutil

                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()

    def pull_image(self, image_name: str, dest_dir: Optional[str] = None) -> str:
        """
        Pull a complete image.

        Args:
            image_name: Image name (e.g., 'nginx:latest')
            dest_dir: Directory to extract image to. Defaults to cache.

        Returns:
            Path to extracted image rootfs
        """
        ref = ImageReference.parse(image_name)
        print(f"Pulling image: {ref.full_name}")

        # Get manifest
        manifest = self.get_manifest(ref)

        # Get config
        config = self.get_config(ref, manifest)

        # Determine destination
        if dest_dir:
            rootfs = Path(dest_dir) / "rootfs"
        else:
            # Use cache
            image_id = manifest.get("config", {}).get("digest", "").replace(":", "_")
            if not image_id:
                image_id = ref.tag or "latest"
            rootfs = (
                self.cache_dir
                / "images"
                / ref.repository.replace("/", "_")
                / image_id
                / "rootfs"
            )

        rootfs.mkdir(parents=True, exist_ok=True)

        # Pull and extract layers in order
        layers = manifest.get("layers", [])
        for i, layer in enumerate(layers):
            print(f"Processing layer {i + 1}/{len(layers)}...")
            layer_path = self.pull_layer(ref, layer, rootfs)
            self.extract_layer(layer_path, rootfs)

        # Save config
        config_path = rootfs.parent / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        print(f"Image pulled to: {rootfs}")
        return str(rootfs)

    def get_image_info(self, image_name: str) -> Dict[str, Any]:
        """
        Get information about an image without pulling it.

        Args:
            image_name: Image name

        Returns:
            Dictionary with image info
        """
        ref = ImageReference.parse(image_name)
        manifest = self.get_manifest(ref)
        config = self.get_config(ref, manifest)

        # Extract useful info
        container_config = config.get("config", {})

        return {
            "reference": ref.full_name,
            "digest": manifest.get("config", {}).get("digest"),
            "created": config.get("created"),
            "architecture": config.get("architecture"),
            "os": config.get("os"),
            "layers": len(manifest.get("layers", [])),
            "env": container_config.get("Env", []),
            "cmd": container_config.get("Cmd", []),
            "entrypoint": container_config.get("Entrypoint", []),
            "working_dir": container_config.get("WorkingDir", ""),
            "exposed_ports": list(container_config.get("ExposedPorts", {}).keys()),
            "labels": container_config.get("Labels", {}),
        }
