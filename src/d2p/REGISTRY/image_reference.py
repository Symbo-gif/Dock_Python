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
Image reference parsing and handling.
Parses Docker image references like 'nginx:latest' or 'docker.io/library/nginx:1.21'.
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class ImageReference:
    """
    Parsed Docker image reference.

    Examples:
        - nginx -> docker.io/library/nginx:latest
        - nginx:1.21 -> docker.io/library/nginx:1.21
        - myuser/myimage:v1 -> docker.io/myuser/myimage:v1
        - gcr.io/project/image@sha256:abc123... -> gcr.io/project/image@sha256:abc123...
    """

    registry: str
    repository: str
    tag: Optional[str] = None
    digest: Optional[str] = None

    DEFAULT_REGISTRY = "docker.io"
    DEFAULT_TAG = "latest"

    @classmethod
    def parse(cls, reference: str) -> "ImageReference":
        """
        Parse a Docker image reference string.

        Args:
            reference: Image reference string (e.g., 'nginx:latest', 'myuser/myimage:v1')

        Returns:
            Parsed ImageReference object.
        """
        if not reference:
            raise ValueError("Empty image reference")

        # Handle digest format (image@sha256:...)
        digest = None
        if "@" in reference:
            ref_part, digest = reference.rsplit("@", 1)
            reference = ref_part

        # Handle tag format (image:tag)
        tag = None
        if ":" in reference:
            # Check if the colon is for a port (e.g., localhost:5000/image)
            # or for a tag
            last_colon = reference.rfind(":")
            before_colon = reference[:last_colon]
            after_colon = reference[last_colon + 1 :]

            # If there's a slash after the colon, it's a port, not a tag
            if "/" not in after_colon and not after_colon.isdigit():
                tag = after_colon
                reference = before_colon

        # Parse registry and repository
        parts = reference.split("/")

        if len(parts) == 1:
            # Just image name: nginx -> docker.io/library/nginx
            registry = cls.DEFAULT_REGISTRY
            repository = f"library/{parts[0]}"
        elif len(parts) == 2:
            # Check if first part is a registry or user
            first_part = parts[0]
            if "." in first_part or ":" in first_part or first_part == "localhost":
                # It's a registry
                registry = first_part
                repository = parts[1]
            else:
                # It's a user/image format
                registry = cls.DEFAULT_REGISTRY
                repository = reference
        else:
            # Full path: registry/path/to/image
            registry = parts[0]
            repository = "/".join(parts[1:])

        # Use default tag if none specified and no digest
        if not tag and not digest:
            tag = cls.DEFAULT_TAG

        return cls(registry=registry, repository=repository, tag=tag, digest=digest)

    @property
    def full_name(self) -> str:
        """Get full image name with registry."""
        name = f"{self.registry}/{self.repository}"
        if self.digest:
            return f"{name}@{self.digest}"
        if self.tag:
            return f"{name}:{self.tag}"
        return name

    @property
    def short_name(self) -> str:
        """Get short image name (without registry if default)."""
        if self.registry == self.DEFAULT_REGISTRY:
            repo = self.repository
            # Remove 'library/' prefix for official images
            if repo.startswith("library/"):
                repo = repo[8:]
            if self.digest:
                return f"{repo}@{self.digest}"
            if self.tag:
                return f"{repo}:{self.tag}"
            return repo
        return self.full_name

    @property
    def registry_url(self) -> str:
        """Get the registry URL for API calls."""
        if self.registry == "docker.io":
            return "https://registry-1.docker.io"
        if "://" in self.registry:
            return self.registry
        return f"https://{self.registry}"

    @property
    def auth_url(self) -> str:
        """Get the authentication URL for the registry."""
        if self.registry == "docker.io":
            return "https://auth.docker.io"
        return self.registry_url

    def __str__(self) -> str:
        return self.short_name

    def __repr__(self) -> str:
        return f"ImageReference({self.full_name})"
