# External Libraries
from setuptools import setup, find_packages
from discord_test import misc

with open("README.rst") as file:
    README = file.read()

with open("requirements.txt") as file:
    REQUIREMENTS = file.readlines()


if __name__ == '__main__':
    setup(
        name="discord_test",
        author="izunadevs",
        author_email="izunadevs@martmists.com",
        maintainer="martmists",
        maintainer_email="mail@martmists.com",
        license="MIT",
        zip_safe=False,
        version=misc.__version__,
        description=misc.description,
        long_description=README,
        url="https://github.com/IzunaDevs/discord.py-test",
        packages=find_packages(),
        install_requires=REQUIREMENTS,
        keywords=[
            "discord", "discord.py", "test", "pytest", "unittest"
        ],
        classifiers=[
            "Development Status :: 2 - Pre-Alpha",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.4",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Framework :: Pytest",
            "Topic :: Software Development :: Testing",
            "Topic :: Software Development :: Libraries :: Python Modules"
        ],
        python_requires=">=3.4")
