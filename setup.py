from setuptools import setup, find_packages

setup(
    name="nps_climate_data",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "earthengine-api",
        "pandas",
        "numpy",
    ],
)
