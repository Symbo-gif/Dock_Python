from setuptools import setup, find_packages

setup(
    name="d2p",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pydantic>=2.0",
        "pyyaml>=6.0",
        "click>=8.0",
        "psutil>=5.9",
        "tenacity>=8.0",
        "python-dotenv>=1.0",
        "jinja2>=3.0",
        "black>=23.0",
    ],
    entry_points={
        "console_scripts": [
            "d2p=d2p.CLI.main:main",
        ],
    },
)
