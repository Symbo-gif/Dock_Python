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
Builders for converting Dockerfiles into internal image models and preparing environments.
Supports executing Dockerfile instructions including FROM, COPY, ADD, RUN, and multi-stage builds.
"""
import os
import subprocess
import shutil
import hashlib
import json
from typing import Optional, Dict, List, Any
from pathlib import Path
from dataclasses import dataclass, field

from ..PARSERS.dockerfile_parser import DockerfileParser
from ..MODELS.container_image import ContainerImage


@dataclass
class BuildContext:
    """Context for a Docker build operation."""

    base_dir: str
    dockerfile_path: str
    image_name: str
    build_args: Dict[str, str] = field(default_factory=dict)
    target_stage: Optional[str] = None
    no_cache: bool = False


@dataclass
class BuildLayer:
    """Represents a layer in the image build process."""

    instruction: str
    digest: str
    size: int
    created_by: str


class LayerCache:
    """Content-addressable cache for build layers."""

    def __init__(self, cache_dir: str):
        """
        Initialize the layer cache.

        Args:
            cache_dir: Directory for cache storage.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "build_cache.json"
        self._index = self._load_index()

    def _load_index(self) -> Dict[str, Any]:
        """Load cache index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"layers": {}}

    def _save_index(self) -> None:
        """Save cache index to disk."""
        with open(self.index_file, "w") as f:
            json.dump(self._index, f, indent=2)

    def get_cache_key(
        self, instruction: str, parent_digest: str, context_hash: Optional[str] = None
    ) -> str:
        """
        Generate a cache key for an instruction.

        Args:
            instruction: The Dockerfile instruction
            parent_digest: Digest of the parent layer
            context_hash: Hash of files involved in the instruction (for COPY/ADD)

        Returns:
            Cache key string
        """
        key_parts = [instruction, parent_digest]
        if context_hash:
            key_parts.append(context_hash)
        key_str = "|".join(key_parts)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, cache_key: str) -> Optional[str]:
        """
        Get a cached layer path.

        Args:
            cache_key: Cache key

        Returns:
            Path to cached layer, or None if not found
        """
        if cache_key in self._index["layers"]:
            path = self._index["layers"][cache_key].get("path")
            if path and Path(path).exists():
                return path
        return None

    def put(self, cache_key: str, layer_path: str, instruction: str) -> None:
        """
        Add a layer to the cache.

        Args:
            cache_key: Cache key
            layer_path: Path to the layer
            instruction: The instruction that created this layer
        """
        self._index["layers"][cache_key] = {
            "path": layer_path,
            "instruction": instruction,
            "created_at": self._get_timestamp(),
        }
        self._save_index()

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def clear(self) -> int:
        """
        Clear all cached layers.

        Returns:
            Number of layers cleared
        """
        count = len(self._index["layers"])
        self._index = {"layers": {}}
        self._save_index()
        return count


class ImageBuilder:
    """
    Analyzes Dockerfiles and builds an internal representation of the image,
    capable of preparing a corresponding native environment.
    """

    def __init__(self, base_dir: str = "."):
        """
        Initializes the ImageBuilder.

        :param base_dir: The base directory for resolving relative paths.
        """
        self.base_dir = base_dir
        self.parser = DockerfileParser()

    def build(self, dockerfile_path: str, image_name: str) -> ContainerImage:
        """
        Parses a Dockerfile and creates a ContainerImage model.

        :param dockerfile_path: Path to the Dockerfile.
        :param image_name: Name to assign to the resulting image.
        :return: A ContainerImage instance.
        """
        full_path = os.path.join(self.base_dir, dockerfile_path)
        instructions = self.parser.parse(full_path)

        image = ContainerImage(name=image_name, base_image="")

        for inst in instructions:
            cmd = inst.instruction
            args = inst.arguments

            if cmd == "FROM":
                image.base_image = args[0]
            elif cmd == "WORKDIR":
                image.working_directory = args[0]
            elif cmd == "ENV":
                # Handle ENV KEY=VALUE or ENV KEY VALUE
                for arg in args:
                    if "=" in arg:
                        k, v = arg.split("=", 1)
                        image.env_vars[k] = v
            elif cmd == "RUN":
                image.run_instructions.append(" ".join(args))
                # Detect pip install
                if "pip install" in " ".join(args):
                    if "-r" in " ".join(args):
                        # Should probably parse requirements file
                        image.pip_requirements.append("from requirements.txt")
            elif cmd == "CMD":
                image.cmd = args
            elif cmd == "ENTRYPOINT":
                image.entrypoint = args

        return image

    def prepare_environment(self, image: ContainerImage):
        """
        Creates a virtual environment for the service and installs dependencies.
        """
        venv_path = os.path.join(self.base_dir, ".d2p", "venvs", image.name)
        print(f"Preparing environment for {image.name} in {venv_path}")

        if not os.path.exists(venv_path):
            os.makedirs(os.path.dirname(venv_path), exist_ok=True)
            subprocess.run(["python", "-m", "venv", venv_path], check=True)

        pip_path = (
            os.path.join(venv_path, "Scripts", "pip.exe")
            if os.name == "nt"
            else os.path.join(venv_path, "bin", "pip")
        )

        for inst in image.run_instructions:
            if "pip install" in inst:
                print(f"Executing dependency installation: {inst}")
                # Replace 'pip' with the actual venv pip path
                cmd = inst.replace("pip", pip_path)
                subprocess.run(cmd, shell=True, check=True)

        # Store venv path in image for later use by process runner
        image.labels["d2p.venv_path"] = venv_path

    def build_with_context(self, context: BuildContext) -> ContainerImage:
        """
        Build an image with full context support including COPY, ADD, and multi-stage builds.

        Args:
            context: Build context with all build parameters.

        Returns:
            Built ContainerImage.
        """
        full_path = os.path.join(context.base_dir, context.dockerfile_path)
        instructions = self.parser.parse(full_path)

        # Initialize layer cache
        cache_dir = os.path.join(context.base_dir, ".d2p", "cache", "build")
        layer_cache = LayerCache(cache_dir)

        # Parse stages for multi-stage builds
        stages: Dict[str, ContainerImage] = {}
        current_stage: Optional[str] = None
        current_image: Optional[ContainerImage] = None
        parent_digest = "base"

        for inst in instructions:
            cmd = inst.instruction
            args = inst.arguments

            if cmd == "FROM":
                # Start new stage
                base_ref = args[0]
                stage_name = None

                # Check for AS clause (multi-stage builds)
                if len(args) >= 3 and args[1].upper() == "AS":
                    stage_name = args[2]

                # Save previous stage if exists
                if current_stage and current_image:
                    stages[current_stage] = current_image

                current_stage = stage_name or f"stage_{len(stages)}"
                current_image = ContainerImage(
                    name=context.image_name, base_image=base_ref
                )
                parent_digest = f"from:{base_ref}"

                # Check if this is a reference to a previous stage
                if base_ref in stages:
                    # Copy from previous stage
                    prev_image = stages[base_ref]
                    current_image.env_vars = prev_image.env_vars.copy()
                    current_image.working_directory = prev_image.working_directory

            elif current_image is None:
                continue

            elif cmd == "WORKDIR":
                current_image.working_directory = args[0]
                parent_digest = self._update_digest(parent_digest, f"workdir:{args[0]}")

            elif cmd == "ENV":
                for arg in args:
                    if "=" in arg:
                        k, v = arg.split("=", 1)
                        # Apply build args substitution
                        v = self._substitute_build_args(v, context.build_args)
                        current_image.env_vars[k] = v
                parent_digest = self._update_digest(parent_digest, f"env:{args}")

            elif cmd == "ARG":
                # Build argument
                arg_str = args[0] if args else ""
                if "=" in arg_str:
                    key, default = arg_str.split("=", 1)
                else:
                    key, default = arg_str, ""
                # Use provided value or default
                if key not in context.build_args:
                    context.build_args[key] = default

            elif cmd == "RUN":
                run_cmd = " ".join(args)
                # Apply build args and env substitution
                run_cmd = self._substitute_build_args(run_cmd, context.build_args)
                current_image.run_instructions.append(run_cmd)
                parent_digest = self._update_digest(parent_digest, f"run:{run_cmd}")

            elif cmd == "COPY":
                # Handle COPY instruction
                self._handle_copy(current_image, args, context, stages)
                parent_digest = self._update_digest(parent_digest, f"copy:{args}")

            elif cmd == "ADD":
                # Handle ADD instruction (similar to COPY but with extra features)
                self._handle_add(current_image, args, context)
                parent_digest = self._update_digest(parent_digest, f"add:{args}")

            elif cmd == "CMD":
                current_image.cmd = args

            elif cmd == "ENTRYPOINT":
                current_image.entrypoint = args

            elif cmd == "EXPOSE":
                for port_str in args:
                    try:
                        port = int(port_str.split("/")[0])
                        current_image.exposed_ports.append(port)
                    except ValueError:
                        pass

            elif cmd == "VOLUME":
                current_image.volumes.extend(args)

            elif cmd == "LABEL":
                for arg in args:
                    if "=" in arg:
                        k, v = arg.split("=", 1)
                        current_image.labels[k] = v.strip("\"'")

            elif cmd == "USER":
                current_image.labels["d2p.user"] = args[0] if args else ""

            elif cmd == "HEALTHCHECK":
                # Store health check info in labels
                current_image.labels["d2p.healthcheck"] = " ".join(args)

        # Save final stage
        if current_stage and current_image:
            stages[current_stage] = current_image

        # Return target stage or final stage
        if context.target_stage and context.target_stage in stages:
            return stages[context.target_stage]

        return current_image or ContainerImage(
            name=context.image_name, base_image="scratch"
        )

    def _update_digest(self, parent: str, instruction: str) -> str:
        """Update the running digest with a new instruction."""
        combined = f"{parent}|{instruction}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _substitute_build_args(self, value: str, build_args: Dict[str, str]) -> str:
        """Substitute build arguments in a value."""
        import re

        # Handle ${VAR} and $VAR syntax
        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            return build_args.get(var_name, match.group(0))

        # Match ${VAR} or $VAR (not followed by more word chars)
        pattern = r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)"
        return re.sub(pattern, replace_var, value)

    def _handle_copy(
        self,
        image: ContainerImage,
        args: List[str],
        context: BuildContext,
        stages: Dict[str, ContainerImage],
    ) -> None:
        """Handle COPY instruction."""
        # Check for --from flag (copy from another stage)
        from_stage = None
        filtered_args = []

        i = 0
        while i < len(args):
            if args[i].startswith("--from="):
                from_stage = args[i].split("=", 1)[1]
            elif args[i] == "--from" and i + 1 < len(args):
                from_stage = args[i + 1]
                i += 1
            elif not args[i].startswith("--"):
                filtered_args.append(args[i])
            i += 1

        if len(filtered_args) < 2:
            return

        sources = filtered_args[:-1]
        dest = filtered_args[-1]

        # Store copy instruction for later execution
        copy_info = {"sources": sources, "dest": dest, "from_stage": from_stage}

        if "d2p.copy_instructions" not in image.labels:
            image.labels["d2p.copy_instructions"] = json.dumps([])

        copies = json.loads(image.labels["d2p.copy_instructions"])
        copies.append(copy_info)
        image.labels["d2p.copy_instructions"] = json.dumps(copies)

    def _handle_add(
        self, image: ContainerImage, args: List[str], context: BuildContext
    ) -> None:
        """Handle ADD instruction (similar to COPY but can handle URLs and tar extraction)."""
        # Filter out flags
        filtered_args = [a for a in args if not a.startswith("--")]

        if len(filtered_args) < 2:
            return

        sources = filtered_args[:-1]
        dest = filtered_args[-1]

        # Store add instruction
        add_info = {
            "sources": sources,
            "dest": dest,
            "type": "add",  # Indicates it's ADD not COPY
        }

        if "d2p.add_instructions" not in image.labels:
            image.labels["d2p.add_instructions"] = json.dumps([])

        adds = json.loads(image.labels["d2p.add_instructions"])
        adds.append(add_info)
        image.labels["d2p.add_instructions"] = json.dumps(adds)

    def execute_copies(
        self, image: ContainerImage, dest_dir: str, build_context_dir: str
    ) -> None:
        """
        Execute stored COPY instructions.

        Args:
            image: The container image with copy instructions
            dest_dir: Destination directory (rootfs)
            build_context_dir: Directory containing build context files
        """
        if "d2p.copy_instructions" not in image.labels:
            return

        copies = json.loads(image.labels["d2p.copy_instructions"])

        for copy_info in copies:
            sources = copy_info["sources"]
            dest = copy_info["dest"]

            # Resolve destination path
            if dest.startswith("/"):
                dest_path = Path(dest_dir) / dest.lstrip("/")
            else:
                work_dir = image.working_directory or "/"
                dest_path = Path(dest_dir) / work_dir.lstrip("/") / dest

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            for source in sources:
                source_path = Path(build_context_dir) / source

                if not source_path.exists():
                    print(f"Warning: COPY source not found: {source}")
                    continue

                if source_path.is_dir():
                    if dest_path.exists() and dest_path.is_dir():
                        shutil.copytree(
                            str(source_path), str(dest_path), dirs_exist_ok=True
                        )
                    else:
                        shutil.copytree(str(source_path), str(dest_path))
                else:
                    if dest.endswith("/") or (
                        dest_path.exists() and dest_path.is_dir()
                    ):
                        dest_path.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(
                            str(source_path), str(dest_path / source_path.name)
                        )
                    else:
                        shutil.copy2(str(source_path), str(dest_path))

    def execute_run_instructions(
        self, image: ContainerImage, rootfs: str, env: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Execute RUN instructions in the image.

        Args:
            image: Container image with run instructions
            rootfs: Path to the rootfs
            env: Additional environment variables

        Returns:
            True if all commands succeeded
        """
        run_env = os.environ.copy()
        run_env.update(image.env_vars)
        if env:
            run_env.update(env)

        work_dir = image.working_directory or "/"
        actual_work_dir = os.path.join(rootfs, work_dir.lstrip("/"))

        for instruction in image.run_instructions:
            print(f"RUN: {instruction}")

            try:
                result = subprocess.run(
                    instruction,
                    shell=True,
                    env=run_env,
                    cwd=actual_work_dir if os.path.exists(actual_work_dir) else rootfs,
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    print(f"Error executing RUN instruction: {instruction}")
                    print(f"stdout: {result.stdout}")
                    print(f"stderr: {result.stderr}")
                    return False

            except Exception as e:
                print(f"Error executing RUN instruction: {e}")
                return False

        return True
