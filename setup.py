from setuptools import find_packages, setup
from subprocess import check_output
import os

name = "meshing_app"
version_file = os.path.join(os.path.dirname(__file__), name, "version.py")

try:
    version = (
        check_output(["git", "describe", "--tags"])
        .decode("utf-8")
        .strip()[1:]
        .split("-")
    )
    version = version[:2]
    version = ".dev".join(version)
    with open(version_file, "w") as f:
        f.write(f'__version__ = "{version}"\n')
except:
    version = open(version_file, "r").read().strip().split("=")[-1].replace('"', "")


setup(
    name=name,
    version=version,
    description="Meshing app for Webapp",
    packages=find_packages("."),
    package_data={ name: ["*.png"] },
    install_requires=[],
    entry_points={"webapp.plugin": ["simple = meshing_app"]},
)
