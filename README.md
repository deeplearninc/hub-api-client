[![CircleCI](https://circleci.com/gh/deeplearninc/hub-api-client.svg?style=shield&circle-token=324fac7562a1de7fe4c3e860628e690ef1094d7e)](https://circleci.com/gh/deeplearninc/hub-api-client)
[![PyPI version](https://badge.fury.io/py/auger-hub-api-client.svg)](https://badge.fury.io/py/auger-hub-api-client)

# API client for Auger Hub API

## Using

### Install

```sh
pip install auger-hub-api-client==0.6.3
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
* `token` - user token, can be obtained with `create_token` request with user credentials
* `hub_project_api_token` - project token (provides project and cluster context to API)
* `hub_cluster_api_token` - cluster token (provides cluster context to API)
* `optimizers_url` - optional, to make `get_next_trials` to optimizers service (requires `hub_project_api_token`)
* `connection_retries_count` - count of connection retries if it makes sense (see `HubApiClient.NetworkError`)
* `retries_count` - count of request retries if it makes sense (see `HubApiClient.RetryableApiError`)
* `retry_wait_seconds` - wait between retries

If app has both tokens prefer `hub_project_api_token`

### Available resources and operations

Full set of available resources, required parameters and parent resource names described here https://app.auger.ai/api/v1/docs

This client currently support only next subset of resources:

* cluster
* cluster_task
* cluster_status
* dataset_manifest
* experiment (ex. notebook)
* experiment_session (ex. project_run)
* hyperparameter
* instance_type
* organization
* pipeline
* prediction
* project
* project_file
* project_file_url
* similar_trials_request
* token
* trial
* trial_search
* warm_start_request

All resource methods called in next convetions:

* `list` - `get_<resource_name>s` list all available resources
* `get` - `get_<resource_name>` get resource by id
* `create` - `create_<resource_name>` creates resource
* `update` - `update_<resource_name>` updates resource
* `delete` - `delete_<resource_name>` deletes resource
* `iterate` - `iterate_all_<resource_name>s` iterate all resources

### List and iterate resources

```python
res = client.get_experiment_sessions()
res['data'] # an array of project runs

# For pagination use offset and limit params
res = client.get_experiment_sessions(offset=100, limit=50)

# You can iterate all objects with
# It will automaticcaly fetch all object and apply a callback to each of them
client.iterate_all_dataset_manifests(
    lambda item: # you code here, item is a dataset manifest object
)

# Some resources are nested (the have a parent resource), so you have to specify the parent id parameter

res = client.get_pipelines(experiment_session_id=1)
```

### Get resource

```python
# Just specify id, and parent id if required
res = self.client.get_pipeline(12313, experiment_session_id=1)
res['data'] # a pipeline object
```

### Create resource

```python
# Specify all required parameters
res = client.create_pipeline(
    id='pipeline-123',
    experiment_session_id='1bf484f7305779',
    trial_id='2c9f4cd18e',
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
res = client.update_experiment_session(4, status='completed')
res['data'] # a project run object
```

### Specific requests

```python
# Update a bunch of trials for project run
# Note trials in plural form
client.update_trials(
    experiment_session_id='1bf484f7305779',
    trials=[ # array of trials data
        {
            'crossValidationFolds': 5,
            'uid': '3D1E99741D37422',
            'classification': True,
            'algorithm_name': 'sklearn.ensemble.ExtraTreesClassifier',
            'score': 0.96,
            'score_name': 'accuracy',
            'algorithm_params': {
                'bootstrap': False,
                'min_samples_leaf': 11,
                'n_estimators': 100,
                'max_features': 0.9907161412382496,
                'criterion': 'gini',
                'min_samples_split': 6
            }
        }
    ]
)
```

### Get resource status

Lightweight endpoint returns only status obf the requested object

```python
client.get_status(object='Project', id=1)
```

Next resources supported:
```
Cluster
ClusterTask
Component
ExperimentSession
Organization
Pipeline
Project
ProjectFile
SimilarTrialsRequest
Subscription
WarmStartRequest
```

### Exceptions

* `HubApiClient.FatalApiError` - retry doesn't make sense in most cases it measn error in source code of consumer or API
* `HubApiClient.InvalidParamsError` - call with invalid params in most cases can be fixed in consumers source code
* `HubApiClient.RetryableApiError` - some network related issue when request retry can make sense like 503 error, timeouts and connection errors
* `HubApiClient.MissingParamError` - client side validation fail, can be fixed only on consumers code side

In all case see exception content it contains more specific details for each case

## Optimizers service 

### Get next trials

```python
client.get_next_trials(
    "optimizer_name": "optimizers_service.optimizers.tpe_hyperopt_optimizer.TPEHyperoptOptimizer",
    "optimizer_params": {
        "batch_size": 1
    },
    "search_space": { /*...*/ },
    "trials_history": [],
    "trial_workers_count": 1,
    "optimizer_context": {},
    "tasks_run_parallel": false
)
```

### Get next trials V2

```python
client.get_next_trials_v2(
    "trials_total_count": 999,
    "trials_limit": 10,
    "search_space": { /*...*/ },
    "trials_history": [ /*...*/ ],
    "optimizer_context": { /*...*/ }
)
```

### Get FTE

```python
res = client.get_fte(
    'alg_name': "sklearn.ensemble.RandomForestClassifier",
    'alg_params': {
        "bootstrap": True,
        "min_samples_leaf": 13,
        "n_estimators": 100,
        "min_samples_split": 3,
        "criterion": "gini",
        "max_features": 0.08361531837907793
    },
    'ncols': 100,
    'nrows': 10000
)

# res['data']['estimated_time'] - result
```


## Releases

* 0.6.3 - Add `get_fte` endpoint
* 0.6.0 - Drop Python 2 support

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
Increase version in **Install** section of readme
Commit and push changes

Create and push new tag

```bash
git tag v0.6.3 && git push origin v0.6.3
```

Then build and upload new wheel
```bash
python3 setup.py sdist bdist_wheel
twine upload dist/*
```
