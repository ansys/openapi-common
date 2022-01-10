import os
import shutil
import sys

from setuptools.config import read_configuration


def item_generator(things):
    for item in things:
        yield item
        yield "\n"


setup_info = read_configuration("../setup.cfg")

install_requires = []
extras_require = {}

if "options" in setup_info:
    info_options = setup_info["options"]
    if "install_requires" in info_options:
        install_requires = info_options["install_requires"]
    if "extras_require" in info_options:
        extras_require = info_options["extras_require"]

# Copy all existing requirements.txt files to allow us to roll-back if something goes wrong
for file in os.listdir("./"):
    if file.endswith("requirements.txt"):
        shutil.move(file, f"./{file}.orig")

try:
    with open("./package_requirements.txt", "w", encoding="utf8") as fp:
        print("Writing package requirements to package_requirements.txt")
        fp.writelines(item_generator(install_requires))

    for extra, requirements in extras_require.items():
        file_name = f"{extra}_requirements.txt"
        print(f"Writing extra requirements for {extra} to {file_name}")
        with open(file_name, "w", encoding="utf8") as fp:
            fp.writelines(item_generator(requirements))

    with open("./.updated", "w") as fp:
        fp.write("updated")

    for file in os.listdir("./"):
        if file.endswith(".orig"):
            os.remove(file)

except (IOError, OSError) as excinfo:
    print("An error occurred:")
    print(excinfo)

    for file in os.listdir("./"):
        if file.endswith(".orig"):
            shutil.move(file, file[:-5])

    print("Rolled back to original state, aborting")
    sys.exit(1)
