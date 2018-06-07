from setuptools import setup

setup(
    name='auger-hub-api-client',
    version='0.1',
    description='API client for Hub API',
    url='https://github.com/deeplearninc/',
    author='DeepLearn',
    author_email='alex@dplrn.com',
    license='Private',
    packages=[
        'auger',
    ],
    install_requires=[
        'requests'
    ],
    zip_safe=False
)
