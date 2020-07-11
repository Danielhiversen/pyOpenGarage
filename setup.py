from setuptools import setup

setup(
    name="open_garage",
    packages=["opengarage"],
    install_requires=[
        "aiohttp>=3.0.6",
        "async_timeout>=1.4.0",
    ],
    version="0.1.5",
    description="A python3 library to communicate with Open Garage",
    python_requires=">=3.5.3",
    author="Daniel Hoyer Iversen",
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
