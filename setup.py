from setuptools import setup, find_packages
import os

def read_requirements():
    with open('requirements.txt') as req:
        content = req.read()
        requirements = content.split('\n')
    return [r for r in requirements if r and not r.startswith('#')]

# Read the contents of your README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="watergun",
    version="0.1.0",
    packages=find_packages(exclude=("tests",)),
    install_requires=read_requirements(),
    entry_points={
        'console_scripts': [
            'watergun=watergun.__main__:main',
        ],
    },
    author="Nile Walker",
    author_email="nilezwalker@gmail.com",
    description="A project for controlling a water gun using computer vision",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stauntonmakerspace/WaterGun",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    include_package_data=True,
    package_data={
        # 'watergun': ['assets/*'],
    },
)