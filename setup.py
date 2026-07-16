from setuptools import setup, find_packages

setup(
    name="maputils",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "Pillow>=9.0.0",
    ],
    extras_require={
        "test": ["pytest"],
    },
)
