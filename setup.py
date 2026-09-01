from setuptools import setup, find_packages

setup(
    name="infrared-remote-control",
    version="0.1.0",
    description="树莓派红外遥控空调",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pigpio",
        "lgpio",
    ],
    entry_points={
        "console_scripts": [
            "ir-remote=infrared.cli:main",
        ],
    },
)