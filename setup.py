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

from setuptools import setup, find_packages

setup(
    name="d2p",
    version="0.1.0",
    description="Docker-to-Python conversion system for running containers as native processes",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Michael Maillet, Damien Davison, Sacha Davison",
    license="Apache-2.0",
    url="https://github.com/Symbo-gif/Dock_Python",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "pydantic>=2.0",
        "pyyaml>=6.0",
        "click>=8.0",
        "psutil>=5.9",
        "tenacity>=8.0",
        "python-dotenv>=1.0",
        "jinja2>=3.0",
    ],
    extras_require={
        "dev": [
            "black>=23.0",
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "pytest-asyncio>=0.21",
            "mypy>=1.0",
            "types-PyYAML>=6.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "d2p=d2p.CLI.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX :: Linux",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Systems Administration",
    ],
)
