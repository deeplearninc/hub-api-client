# Warm start request

```python
# Create request
warm_start_request = client.create_warm_start_request(
  dataset_manifest_id='100500',
  score_name='logloss',
  limit=5
)

# warm_start_request => 
# {
#   "data": {
#     "object": "warm_start_request",
#     "deleted": false,
#     "id": 1,
#     "score_name": "logloss",
#     "limit": 5,
#     "status": "requested",
#     "time_consumed_ms": null,
#     "hyperparameters": []
#   },
#   "meta": {
#     "status": 200
#   }
# }

# After some time get it again by id until the status will not be `done` or `error`
warm_start_request = client.get_warm_start_request(warm_start_request.id)

# result will be in `hyperparameters` field 
# warm_start_request => 
# {
#   "data": {
#     "object": "warm_start_request",
#     "deleted": false,
#     "id": 1,
#     "score_name": "logloss",
#     "limit": 5,
#     "status": "done",
#     "time_consumed_ms": 1200,
#     "hyperparameters": [
#       {
#         "object": "hyperparameter",
#         "deleted": false,
#         "id": 1,
#         "algorithm_name": "SVM",
#         "algorithm_params": {
#           "x": 1,
#           "y": 2
#         }   
#       }
#     ]
#   },
#   "meta": {
#     "status": 200
#   }
# }

```
