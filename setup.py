"""A setuptools based setup module for pygobgp"""
# !/usr/bin/env python
# -*- coding: utf-8 -*-

from codecs import open
from os import path
from setuptools import setup, find_packages


requirements = [
    "grpcio==1.15.0",
    "grpcio-tools==1.15.0",
    "googleapis-common-protos==1.5.3",
]


setup(
    name='pygobgp',
    version="0.1.1",
    description="Python library to interact GoBGP",
    author="Mehmet Oner Yalcin",
    author_email='oneryalcin@gmail.com',
    url="",
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    include_package_data=True,
    platforms='Linux',
    install_requires=requirements,
    license="Apache",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Telecommunications Industry',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)

