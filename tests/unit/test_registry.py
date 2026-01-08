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
Unit tests for the registry module.
"""
import pytest
from d2p.REGISTRY.image_reference import ImageReference


class TestImageReference:
    """Tests for ImageReference parsing."""

    def test_parse_simple_name(self):
        """Test parsing a simple image name."""
        ref = ImageReference.parse("nginx")
        assert ref.registry == "docker.io"
        assert ref.repository == "library/nginx"
        assert ref.tag == "latest"

    def test_parse_with_tag(self):
        """Test parsing image with tag."""
        ref = ImageReference.parse("nginx:1.21")
        assert ref.registry == "docker.io"
        assert ref.repository == "library/nginx"
        assert ref.tag == "1.21"

    def test_parse_user_image(self):
        """Test parsing user/image format."""
        ref = ImageReference.parse("myuser/myimage:v1")
        assert ref.registry == "docker.io"
        assert ref.repository == "myuser/myimage"
        assert ref.tag == "v1"

    def test_parse_full_reference(self):
        """Test parsing full registry reference."""
        ref = ImageReference.parse("gcr.io/project/image:latest")
        assert ref.registry == "gcr.io"
        assert ref.repository == "project/image"
        assert ref.tag == "latest"

    def test_parse_with_digest(self):
        """Test parsing image with digest."""
        ref = ImageReference.parse("nginx@sha256:abc123")
        assert ref.registry == "docker.io"
        assert ref.repository == "library/nginx"
        assert ref.digest == "sha256:abc123"
        assert ref.tag is None

    def test_parse_localhost_registry(self):
        """Test parsing localhost registry."""
        ref = ImageReference.parse("localhost:5000/myimage:v1")
        assert ref.registry == "localhost:5000"
        assert ref.repository == "myimage"
        assert ref.tag == "v1"

    def test_full_name(self):
        """Test full_name property."""
        ref = ImageReference.parse("nginx:1.21")
        assert ref.full_name == "docker.io/library/nginx:1.21"

    def test_short_name(self):
        """Test short_name property."""
        ref = ImageReference.parse("nginx:1.21")
        assert ref.short_name == "nginx:1.21"

        ref2 = ImageReference.parse("myuser/myimage:v1")
        assert ref2.short_name == "myuser/myimage:v1"

    def test_registry_url(self):
        """Test registry_url property."""
        ref = ImageReference.parse("nginx")
        assert ref.registry_url == "https://registry-1.docker.io"

        ref2 = ImageReference.parse("gcr.io/project/image")
        assert ref2.registry_url == "https://gcr.io"

    def test_empty_reference_raises(self):
        """Test that empty reference raises error."""
        with pytest.raises(ValueError):
            ImageReference.parse("")

    def test_str_representation(self):
        """Test string representation."""
        ref = ImageReference.parse("nginx:1.21")
        assert str(ref) == "nginx:1.21"
