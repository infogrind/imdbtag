import os
from setuptools import setup, find_packages

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as f:
    description = f.read()

setup(
    name='imdbtag',
    version="1.2",
    author=__import__('PTN').__author__,
    author_email=__import__('PTN').__email__,
    url='https://github.com/infogrind/imdbtag',
    description='A simple file/directory renamer based on The Movie Database (TMDb)',
    long_description=description,
    packages=find_packages(),
    install_requires = [
        "parse-torrent-name",
        "simplejson", # transitive dependency of tmdb
        "fuzzywuzzy", # transitive dependency of tmdb
        "requests" # transitive dependency of tmdb
        ],
    entry_points={
        "console_scripts": ["imdbtag = imdbtag:main"]
        },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Natural Language :: English'
        ]
    )
