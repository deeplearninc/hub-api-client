import os
import sys
from setuptools import setup
from setuptools.command.install import install

VERSION = '0.7.2'

class VerifyVersionCommand(install):
    """Verify that the git tag matches our version"""
    description = 'verify that the git tag matches our version'

    def run(self):
        tag = os.getenv('CIRCLE_TAG', '')

        if not tag.endswith(VERSION, 1):
            info = "Git tag: {0} does not match the version of auger-cli: {1}".format(
                tag, VERSION
            )
            sys.exit(info)

setup(
    name='auger-hub-api-client',
    version=VERSION,
    description='API client for Auger Hub API',
    long_description='API client for Auger Hub API. Auger is an Automated Machine Learning tool https://auger.ai/',
    url='https://github.com/deeplearninc/',
    author='DeepLearn Inc.',
    author_email='alex@dplrn.com',
    license='MIT',
    packages=[
        'auger.hub_api_client',
    ],
    install_requires=[
        'requests',
        'beautifulsoup4',
        'lxml'
    ],
    zip_safe=False,
    cmdclass={
        'verify': VerifyVersionCommand
    }
)
