from setuptools import setup

setup(
    name='auger-hub-api-client',
    version='0.5.0',
    description='API client for Auger Hub API',
    long_description='API client for Auger Hub API. Auger is an Automated Machine Learning tool https://auger.ai/',
    url='https://github.com/deeplearninc/',
    author='DeepLearn Inc.',
    author_email='alex@dplrn.com',
    license='MIT',
    packages=[
        'auger',
    ],
    install_requires=[
        'requests'
    ],
    zip_safe=False
)
