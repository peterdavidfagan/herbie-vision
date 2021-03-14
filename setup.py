import setuptools
from setuptools import setup
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='herbie_vision',
    version='0.1.6',    
    description='Package for 2d object detection',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Ethan Garrity / Peter David Fagan / Tiffany Han Shi',
    author_email='peterdavidfagan@gmail.com',
    packages=setuptools.find_packages(),
    py_modules=['herbie_vision'],
    license='MIT',
    python_requires='>=3.5',
)