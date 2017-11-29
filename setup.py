# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


setup(
    name='lamp',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'lamp': [
            'static/*.html'
        ]
    },
    install_requires=[
        'Click',
        'Tornado',
    ],
    entry_points='''
        [console_scripts]
        lamp=lamp.cli:cli
    ''',
)
