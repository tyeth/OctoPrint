# coding=utf-8
from setuptools import setup

plugin_identifier = "snapmaker_cnc_probe"
plugin_package = "snapmaker_cnc_probe"
plugin_name = "Snapmaker CNC Probe"
plugin_version = "0.1.0"
plugin_description = "OctoPrint plugin for CNC probing with Snapmaker"
plugin_author = "Tyeth Gundry"
plugin_author_email = "your.email@example.com"
plugin_url = "https://github.com/yourusername/snapmaker_cnc_probe"
plugin_license = "MIT"

plugin_requires = [
    "OctoPrint>=1.5.0",
    "pyserial>=3.4",
    "opencv-python>=4.5.1.48"
]

# Additional extras
# For example:
# plugin_requires_extra = {'develop': ['pytest', 'mock']}

# Additional package data to install for this plugin
# Examples:
# plugin_additional_data = {'templates': ['templates/*.jinja2']}
plugin_additional_data = {}

plugin_ignored_packages = []
additional_setup_parameters = {"python_requires": ">=3.7,<4"}

try:
    import octoprint_setuptools
except:
    print("Could not import OctoPrint's setuptools, are you sure you are running that under "
          "the same python installation that OctoPrint is installed under?")
    import sys
    sys.exit(-1)

setup_parameters = octoprint_setuptools.create_plugin_setup_parameters(
    identifier=plugin_identifier,
    package=plugin_package,
    name=plugin_name,
    version=plugin_version,
    description=plugin_description,
    author=plugin_author,
    mail=plugin_author_email,
    url=plugin_url,
    license=plugin_license,
    requires=plugin_requires,
    additional_packages=plugin_ignored_packages,
    ignored_packages=plugin_ignored_packages,
    additional_data=plugin_additional_data,
    extra_requires=plugin_requires_extra if "plugin_requires_extra" in locals() else {},
    **additional_setup_parameters
)

setup(**setup_parameters)