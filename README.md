[![CircleCI](https://circleci.com/gh/deeplearninc/hub-api-client.svg?style=shield&circle-token=324fac7562a1de7fe4c3e860628e690ef1094d7e)](https://circleci.com/gh/deeplearninc/hub-api-client)

# API client for Auger Hub API

## Using

### Install

```sh
pip install git+https://github.com/deeplearninc/hub-api-client#egg=auger-hub-api-client
```
### Initialize client

```python
from auger.hub_api_client import HubApiClient

# Create client instance
client = HubApiClient(
    hub_app_url='http://localhost:5000',
    hub_project_api_token='some secret token'
)
```

Client parameters:

* `hub_app_url` - URL of Hub API server (e.g. http://localhost:5000 or https://app.auger.ai/)
* `hub_project_api_token` - project token (provides project and cluster context to API)
* `hub_cluster_api_token` - cluster token (provides cluster context to API)

If app has both tokens prefer `hub_project_api_token`

### Available resources and operations

Full set of available resources, required parameters and parent resource names described here https://app.auger.ai/api/v1/docs

This client currently support only next subset:

* dataset_manifest
* hyperparameter
* project_run
* pipeline
* trial

All resource methods called in next convetions:

* `list` - `get_<resource_name>s` list all available resources
* `get` - `get_<resource_name>` get resource by id
* `create` - `create_<resource_name>` creates resource
* `update` - `update_<resource_name>` updates resource
* `iterate` - `iterate_all_<resource_name>s` iterate all resources

### List and iterate resources

```python
res = client.get_project_runs()
res['data'] # an array of project runs

# For pagination use offset and limit params
res = client.get_project_runs(offset=100, limit=50)

# You can iterate all objects with
# It will automaticcaly fetch all object and apply a callback to each of them
client.iterate_all_dataset_manifests(
    lambda item: # you code here, item is a dataset manifest object
)

# Some resources are nested (the have a parent resource), so you have to specify the parent id parameter

res = client.get_pipelines(project_run_id=1)
```

### Get resource

```python
# Just specify id, and parent id if required
res = self.client.get_pipeline(12313, project_run_id=1)
res['data'] # a pipeline object 
```

### Create resource

```python
# Specify all required parameters
res = client.create_pipeline(
    id='pipeline-123',
    project_run_id=1,
    dataset_manifest_id=100500,
    trial={
        'task_type': 'subdue leather bags',
        'evaluation_type': 'fastest one',
        'score_name': 'strict one',
        'score_value': 99.9,
        'hyperparameter': {
            'algorithm_name': 'SVM',
            'algorithm_params': {
                'x': 1,
                'y': 2,
            }
        }
    }
)

res['data'] # a pipeline object 
```

### Update resource

```python
res = client.update_project_run(4, status='completed')
res['data'] # a project run object
```

### Specific requests

```python
# Update a bunch of trials for project run
# Note trials in plural form
client.update_trials(
    project_run_id=1, # project run id
    dataset_manifest_id=100500,
    trials=[ # array of trials data
        {
            'task_type': 'subdue leather bags',
            'evaluation_type': 'fastest one',
            'score_name': 'strict one',
            'score_value': 99.9,
            'hyperparameter': {
                'algorithm_name': 'SVM',
                'algorithm_params': {
                    'x': 1,
                    'y': 2,
                }
            }
        }
    ]
)
```
### Excpetions

* `HubApiClient.FatalApiError` - retry doesn't make sense in most cases it measn error in source code of consumer or API
* `HubApiClient.InvalidParamsError` - call with invalid params in most cases can be fixed in consumers source code
* `HubApiClient.RetryableApiError` - some network related issue when request retry can make sense
* `HubApiClient.MissingParamError` - client side validation fail, can be fixed only on consumers code side

In all case see exception content it contains more specific details for each case

## Development

Create virtualenv:
```sh
python3 -m venv .venv
```

Activate virtualenv:
```sh
source .venv/bin/activate
```

The following will install the necessary python dependencies:

```bash
make install
```

Run tests

```bash
make test
```

## Release

Increase version in `setup.py` then build and upload package

```bash
python3 setup.py sdist bdist_wheel
twine upload dist/*
```
