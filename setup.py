from setuptools import setup, find_packages

setup(
    name="cli-assist",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "click",
    ],
    entry_points={
        "console_scripts": [
            "cliassist=ai_backend.__main__:main",
        ],
    },
)
