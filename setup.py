"""InkForge — 开箱即用的涌现式小说生成系统。"""
from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="inkforge",
    version="1.0.0",
    author="Edward A. Thomson",
    description="LLM 驱动的中文长篇小说涌现式生成系统",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/lightlanguage1/InkForge",
    packages=find_packages(exclude=["tests*", "scripts*"]),
    include_package_data=True,
    package_data={
        "novel_agent": ["data/**/*"],
    },
    python_requires=">=3.10",
    install_requires=[
        "typer>=0.9.0",
        "pyyaml>=6.0.0",
        "jsonschema>=4.0.0",
        "openai>=1.0.0",
        "chromadb>=0.4.0",
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.20.0",
        "pydantic>=2.0.0",
        "sse-starlette>=1.0.0",
    ],
    extras_require={
        "gemini": ["google-generativeai>=0.3.0"],
        "claude": ["anthropic>=0.20.0"],
        "all": [
            "google-generativeai>=0.3.0",
            "anthropic>=0.20.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "httpx>=0.24.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "novel=novel_agent.cli.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Text Processing :: Linguistic",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
