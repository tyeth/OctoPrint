# coding=utf-8
from setuptools import setup, find_packages

setup(
    name="Snapmaker-CNC-Probe",
    version="0.1.0",
    description="OctoPrint plugin for CNC probing with Snapmaker",
    author="Tyeth Gundry",
    author_email="your.email@example.com",
    url="https://github.com/tyeth/snapmaker_cnc_probe",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "OctoPrint>=1.5.0",
        "pyserial>=3.4",
        "opencv-python>=4.5.1.48"
    ],
    entry_points={
        "octoprint.plugin": [
            "snapmaker_cnc_probe=octoprint_snapmaker_cnc_probe:SnapmakerProbePlugin"
        ]
    }
)