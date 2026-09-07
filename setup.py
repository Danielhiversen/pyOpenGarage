from setuptools import setup

setup(
    name="open_garage",
    packages=["opengarage"],
    install_requires=["aiohttp>=3.14.3", "async_timeout>=5.0.1"],
    entry_points={
        "console_scripts": ["opengarage=opengarage.cli:main"],
    },
    extras_require={
        "dev": [
            "dlint>=0.16.0",
            "flake8>=7.3.0",
            "flake8-bandit>=4.1.1",
            "flake8-bugbear>=25.11.29",
            "flake8-deprecated>=2.3.0",
            "flake8-executable>=2.1.3",
            "isort>=9.0.1",
            "pylint>=4.0.8",
            "pytest>=9.1.1",
            "pytest-asyncio>=1.4.0",
            "pytest-cov>=7.1.0"
        ]
    },
    version="0.2.0",
    description="A python3 library to communicate with Open Garage",
    python_requires=">=3.5.3",
    author="Daniel Hjelseth Høyer",
    author_email="mail@dahoiv.net",
    url="https://github.com/Danielhiversen/pyOpenGarage",
    license="MIT",
    classifiers=[
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Topic :: Home Automation",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
