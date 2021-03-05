import json
import random
import re
import sys
import unittest
from mock import patch

from auger.hub_api_client import HubApiClient
from tests.vcr_helper import vcr

string_type = str

class TestRetryCounter(unittest.TestCase):
    def createCounter(self, retries_count, connection_retries_count):
        client = HubApiClient(
            hub_app_url='https://some-url.com',
            retries_count=retries_count,
            connection_retries_count=connection_retries_count
        )

        return HubApiClient.RetryCounter(client)

    def test_none_counter(self):
        counter = HubApiClient.RetryCounter.none()
        self.assertEqual(counter.is_retries_available(), False)

    def test_counter_retry(self):
        counter = self.createCounter(retries_count=1, connection_retries_count=2)
        self.assertEqual(counter.is_retries_available(), True)

        counter.count_retry(HubApiClient.RetryableApiError('some error'))
        self.assertEqual(counter.is_retries_available(), False)

    def test_counter_connection_retry(self):
        counter = self.createCounter(retries_count=1, connection_retries_count=2)
        self.assertEqual(counter.is_retries_available(), True)

        counter.count_retry(HubApiClient.NetworkError('some error'))
        self.assertEqual(counter.is_retries_available(), True)

        counter.count_retry(HubApiClient.NetworkError('some error'))
        self.assertEqual(counter.is_retries_available(), False)

    def test_counter_unlnown_retry(self):
        counter = self.createCounter(retries_count=1, connection_retries_count=2)

        with self.assertRaises(RuntimeError) as context:
            counter.count_retry(HubApiClient.InvalidParamsError('some error'))
            self.assertIn('Unsupported kind of error', str(context.error))


@patch('time.sleep', return_value=None)
class TestHubApiClient(unittest.TestCase):
    def setUp(self):
        self.hub_project_api_token = '0d5a55cb795f2039922689e647cb3c5d24a0992bf58d941dad864ef7c371f8fc'

        self.client = HubApiClient(
          hub_app_url='http://localhost:5000',
          optimizers_url='http://localhost:7777',
          retries_count=1,
          hub_project_api_token=self.hub_project_api_token
        )

    def assertInvalidParams(self, metadata, expected_params):
        actual_params = list(map(lambda error: error['error_param'], metadata['errors']))
        self.assertEqual(actual_params, expected_params)

    def assertIndexResponse(self, res, expected_object):
        self.assertEqual(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], list)
        self.assertTrue(len(res['data']) > 0)
        self.assertEqual(res['data'][0]['object'], expected_object)

    def assertResourceResponse(self, res, expected_object):
        self.assertEqual(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], dict)
        self.assertEqual(res['data']['object'], expected_object)

    def assertResourceEmptyResponse(self, res, expected_object):
        self.assertEqual(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], dict)

    def assertDataResponse(self, res, expected_keys):
        self.assertEqual(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], dict)
        for expected_key in expected_keys:
            expected_value = expected_keys[expected_key]
            if isinstance(expected_value, type):
                self.assertIsInstance(res['data'][expected_key], expected_value)
            else:
                self.assertEqual(res['data'][expected_key], expected_value)

    def assertUnauthenticatedResponse(self, metadata):
        self.assertEqual(metadata['status'], 401)
        error = metadata['errors'][0]
        self.assertEqual(error['error_type'], 'unauthenticated')
        self.assertIsInstance(error['message'], string_type)

    def assertServerErrorResponse(self, error):
        self.assertIn('status: 503', str(error))
        self.assertIn('Application Error', str(error))

    # Auth with token

    @vcr.use_cassette('auth/token_valid.yaml')
    def test_auth_token_valid(self, sleep_mock):
        client = HubApiClient(
            hub_app_url='http://localhost:5000',
            token='eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6ImhlckBtYWlsLmNvbSIsImV4cCI6MTU1NTIzNjI0NH0.SyZ5e1-zbuFEy7Q176fcuToehpdwrSIa-CK-qTs0D_E'
        )

        res = client.get_experiments()
        self.assertIndexResponse(res, 'experiment')

    @vcr.use_cassette('auth/token_invalid.yaml')
    def test_auth_token_invalid(self, sleep_mock):
        client = HubApiClient(
            hub_app_url='http://localhost:5000',
            token='wrong'
        )

        with self.assertRaises(HubApiClient.FatalApiError) as context:
            client.get_experiments()

        self.assertUnauthenticatedResponse(context.exception.metadata())

    # Connection error, timeout and similar errors
    @vcr.use_cassette('general_errors/network_unavailable.yaml')
    def test_network_unavailable(self, sleep_mock):
        client = HubApiClient(
            hub_app_url='http://ivalid-url',
            token='some-token',
            retries_count=2,
        )

        with self.assertRaises(HubApiClient.NetworkError) as context:
            client.get_trials()

    # 503 error and similar errors
    @vcr.use_cassette('general_errors/server_unavailable.yaml')
    def test_server_unavailable(self, sleep_mock):
        client = HubApiClient(
            hub_app_url='https://optimizers-service-prod.herokuapp.com',
            token='some-token',
            retries_count=2,
        )

        with self.assertRaises(HubApiClient.RetryableApiError) as context:
            client.get_trials()

        self.assertServerErrorResponse(context.exception)

    # Cluster statuses

    @vcr.use_cassette('cluster_statuses/index.yaml')
    def test_get_cluster_statuses(self, sleep_mock):
        res = self.client.get_cluster_statuses(cluster_id=340)
        self.assertIndexResponse(res, 'cluster_status')

    # Cluster tasks

    @vcr.use_cassette('cluster_tasks/show.yaml')
    def test_get_cluster_task(self, sleep_mock):
      res = self.client.get_cluster_task(25)
      self.assertResourceResponse(res, 'cluster_task')

    @vcr.use_cassette('cluster_tasks/index.yaml')
    def test_get_cluster_tasks(self, sleep_mock):
        res = self.client.get_cluster_tasks()
        self.assertIndexResponse(res, 'cluster_task')

    @vcr.use_cassette('cluster_tasks/create_valid.yaml')
    def test_create_cluster_task_valid(self, sleep_mock):
        res = self.client.create_cluster_task(
            name='auger_ml.tasks_queue.tasks.list_project_files',
            queue=None,
            args=None
        )

        self.assertResourceResponse(res, 'cluster_task')

    @vcr.use_cassette('cluster_tasks/update_valid.yaml')
    def test_update_cluster_task_valid(self, sleep_mock):
        res = self.client.update_cluster_task(
            id=55,
            status='success',
            result={ 'x': 1, 'y': 2 },
            traceback='Some str\nSome more data'
        )

        self.assertResourceResponse(res, 'cluster_task')

    # Dataset manifests

    @vcr.use_cassette('dataset_manifests/show.yaml')
    def test_get_dataset_manifest(self, sleep_mock):
      res = self.client.get_dataset_manifest(100500)
      self.assertResourceResponse(res, 'dataset_manifest')

    @vcr.use_cassette('dataset_manifests/index.yaml')
    def test_get_dataset_manifests(self, sleep_mock):
        res = self.client.get_dataset_manifests()
        self.assertIndexResponse(res, 'dataset_manifest')

    @vcr.use_cassette('dataset_manifests/all_index.yaml')
    def test_iterate_all_dataset_manifests(self, sleep_mock):
        self.client.iterate_all_dataset_manifests(
          lambda item: self.assertEqual(item['object'], 'dataset_manifest'),
          limit=1
        )

    @vcr.use_cassette('dataset_manifests/create_invalid.yaml')
    def test_create_dataset_manifest_invalid(self, sleep_mock):
        with self.assertRaises(HubApiClient.InvalidParamsError) as context:
            self.client.create_dataset_manifest()

        self.assertInvalidParams(context.exception.metadata(), ['id', 'name', 'statistics'])

    @vcr.use_cassette('dataset_manifests/create_valid.yaml')
    def test_create_dataset_manifest_valid(self, sleep_mock):
        res = self.client.create_dataset_manifest(
            id=100500,
            name='test',
            statistics={'x': 1, 'y': 2}
        )

        self.assertResourceResponse(res, 'dataset_manifest')

    @vcr.use_cassette('dataset_manifests/update_valid.yaml')
    def test_update_dataset_manifest_valid(self, sleep_mock):
        res = self.client.update_dataset_manifest(123123, dataset_url='s3://bucket/path')
        self.assertResourceResponse(res, 'dataset_manifest')

    # Endpoints

    @vcr.use_cassette('endpoints/show.yaml')
    def test_get_endpoint(self, sleep_mock):
      res = self.client.get_endpoint('ddc968ac-43d5-4aa4-9929-1edba7cefc8f')
      self.assertResourceResponse(res, 'endpoint')

    @vcr.use_cassette('endpoints/index.yaml')
    def test_get_endpoints(self, sleep_mock):
        res = self.client.get_endpoints()
        self.assertIndexResponse(res, 'endpoint')

    @vcr.use_cassette('endpoints/create_valid.yaml')
    def test_create_endpoint_valid(self, sleep_mock):
        res = self.client.create_endpoint(
            pipeline_id='118DCF6B1A2A44A',
            name='test-endpoint',
        )

        self.assertResourceResponse(res, 'endpoint')

    @vcr.use_cassette('endpoints/update_valid.yaml')
    def test_update_endpoint_valid(self, sleep_mock):
        res = self.client.update_endpoint('3a0cfb34-b03b-468c-8e13-2befe3e78819', name='my super endpoint')
        self.assertResourceResponse(res, 'endpoint')

    @vcr.use_cassette('endpoints/delete.yaml')
    def test_delete_endpoint_valid(self, sleep_mock):
        res = self.client.delete_endpoint('3a0cfb34-b03b-468c-8e13-2befe3e78819')
        self.assertResourceResponse(res, 'endpoint')

    # Endpoint pipelines

    @vcr.use_cassette('endpoint_pipelines/create_valid.yaml')
    def test_create_endpoint_pipeline_valid(self, sleep_mock):
        res = self.client.create_endpoint_pipeline(
            endpoint_id='ddc968ac-43d5-4aa4-9929-1edba7cefc8f',
            pipeline_id='118DCF6B1A2A44A',
            active=True,
        )

        self.assertResourceResponse(res, 'endpoint_pipeline')

    @vcr.use_cassette('endpoint_pipelines/update_valid.yaml')
    def test_update_endpoint_pipeline_valid(self, sleep_mock):
        res = self.client.update_endpoint_pipeline(7, active=True)
        self.assertResourceResponse(res, 'endpoint_pipeline')

    @vcr.use_cassette('endpoint_pipelines/delete.yaml')
    def test_delete_endpoint_pipeline_valid(self, sleep_mock):
        res = self.client.delete_endpoint_pipeline(3)
        self.assertResourceResponse(res, 'endpoint_pipeline')

    # Endpoint predictions + actuals

    @vcr.use_cassette('endpoint_predictions/show.yaml')
    def test_get_endpoint_prediction(self, sleep_mock):
        res = self.client.get_endpoint_prediction(
            '46da6a3f-085b-4169-8157-4d20deba3bd1',
            endpoint_id='ddc968ac-43d5-4aa4-9929-1edba7cefc8f'
        )
        self.assertResourceResponse(res, 'prediction_group')

    @vcr.use_cassette('endpoint_predictions/index.yaml')
    def test_get_endpoint_predictions(self, sleep_mock):
        res = self.client.get_endpoint_predictions(endpoint_id='ddc968ac-43d5-4aa4-9929-1edba7cefc8f')
        self.assertIndexResponse(res, 'prediction_group')

    @vcr.use_cassette('endpoint_predictions/create_valid.yaml')
    def test_create_endpoint_prediction_valid(self, sleep_mock):
        res = self.client.create_endpoint_prediction(
            endpoint_id='ddc968ac-43d5-4aa4-9929-1edba7cefc8f',
            records=[[1.1, 1.2, 1.3, 1.4]],
            features=['sepal_length', 'sepal_length', 'petal_length', 'petal_width']
        )

        self.assertResourceResponse(res, 'prediction_group')

    @vcr.use_cassette('endpoint_actuals/create_valid.yaml')
    def test_create_endpoint_actuals_valid(self, sleep_mock):
        res = self.client.create_endpoint_actual(
            endpoint_id='ddc968ac-43d5-4aa4-9929-1edba7cefc8f',
            prediction_group_id='46da6a3f-085b-4169-8157-4d20deba3bd1',
            actuals=[{'prediction_id': '1', 'endpoint_actual': 1},
                     {'prediction_id': '2', 'endpoint_actual': 1}]
        )

        self.assertResourceEmptyResponse(res, 'actual')

    @vcr.use_cassette('endpoint_actuals/delete.yaml')
    def test_delete_endpoint_actuals_valid(self, sleep_mock):
        res = self.client.delete_endpoint_actuals(
            'ddc968ac-43d5-4aa4-9929-1edba7cefc8f',
            **{
                'from': '2020-08-10',
                'to': '2020-08-20',
                'with_predictions': True,
            }
        )

        self.assertIndexResponse(res, 'cluster_task')

    # Endpoint ROI validations

    @vcr.use_cassette('endpoint_roi_validations/create.yaml')
    def test_create_endpoint_roi_validations(self, sleep_mock):
        res = self.client.create_endpoint_roi_validation(
            endpoint_id='8cbb0609-f0b9-42a6-952a-373c20ab7806',
            expressions=['P = true', '$1000', '@if(A = true, $1050, $0)'],
        )

        self.assertResourceResponse(res, 'cluster_task')

    # Experiments

    @vcr.use_cassette('experiments/show.yaml')
    def test_get_experiment(self, sleep_mock):
        res = self.client.get_experiment('0138f8da7adf76')
        self.assertResourceResponse(res, 'experiment')

    @vcr.use_cassette('experiments/index.yaml')
    def test_get_experiments(self, sleep_mock):
        res = self.client.get_experiments()
        self.assertIndexResponse(res, 'experiment')

    @vcr.use_cassette('experiments/create_valid.yaml')
    def test_create_experiment_valid(self, sleep_mock):
        res = self.client.create_experiment(
            id='a0138f7adf78d6',
            dataset_manifest_id='c993ab1107',
            name='Some sort of experiment'
        )

        self.assertResourceResponse(res, 'experiment')

    @vcr.use_cassette('experiments/update_valid.yaml')
    def test_update_experiment_valid(self, sleep_mock):
        res = self.client.update_experiment('a0138f7adf78d6', name='Real experiment')
        self.assertResourceResponse(res, 'experiment')

    @vcr.use_cassette('experiments/delete_valid.yaml')
    def test_delete_experiment_valid(self, sleep_mock):
        res = self.client.delete_experiment('a0138f7adf78d6')
        self.assertResourceResponse(res, 'experiment')

    @vcr.use_cassette('experiments/delete_not_existing.yaml')
    def test_delete_not_existing(self, sleep_mock):
        with self.assertRaises(HubApiClient.FatalApiError) as context:
            self.client.delete_experiment('a0138f7adf78d6')

    # Experiment Sessions

    @vcr.use_cassette('experiment_sessions/show.yaml')
    def test_get_experiment_session(self, sleep_mock):
        res = self.client.get_experiment_session('5772fd1ec439b7')
        self.assertResourceResponse(res, 'experiment_session')

    @vcr.use_cassette('experiment_sessions/index.yaml')
    def test_get_experiment_sessions(self, sleep_mock):
        res = self.client.get_experiment_sessions()
        self.assertIndexResponse(res, 'experiment_session')

    @vcr.use_cassette('experiment_sessions/index_with_filter.yaml')
    def test_get_experiment_sessions_with_filter(self, sleep_mock):
        res = self.client.get_experiment_sessions(project_id=31)
        self.assertIndexResponse(res, 'experiment_session')

    @vcr.use_cassette('experiment_sessions/create_malformed_json.yaml')
    def test_create_experiment_session_malformed_json(self, sleep_mock):
        with self.assertRaises(HubApiClient.FatalApiError) as context:
            self.client.create_experiment_session(
                id='1984368722',
                experiment_id='afaf-dfgdfhg-gdfgdg',
                dataset_manifest_id='c993ab1107',
                status='running',
                leaderbord={'a1': 1, 'a2': 2},
                model_settings={'x': float('inf')},
                message='Some sort of message'
            )

    @vcr.use_cassette('experiment_sessions/create_valid.yaml')
    def test_create_experiment_session_valid(self, sleep_mock):
        res = self.client.create_experiment_session(
            id='1984368722',
            experiment_id='0138f8da7adf76',
            dataset_manifest_id='c993ab1107',
            status='started',
            leaderbord={'a1': 1, 'a2': 2},
            model_settings={'x': 1, 'y': 2},
            message='Some sort of message'
        )

        self.assertResourceResponse(res, 'experiment_session')

    @vcr.use_cassette('experiment_sessions/update_valid.yaml')
    def test_update_experiment_session_valid(self, sleep_mock):
        res = self.client.update_experiment_session('1984368722', status='completed')
        self.assertResourceResponse(res, 'experiment_session')

    # Hyperparameters

    @vcr.use_cassette('hyperparameters/show.yaml')
    def test_get_hyperparameter(self, sleep_mock):
        res = self.client.get_hyperparameter(1)
        self.assertResourceResponse(res, 'hyperparameter')

    @vcr.use_cassette('hyperparameters/index.yaml')
    def test_get_hyperparameters(self, sleep_mock):
        res = self.client.get_hyperparameters()
        self.assertIndexResponse(res, 'hyperparameter')

    @vcr.use_cassette('hyperparameters/create_valid.yaml')
    def test_create_hyperparameter_valid(self, sleep_mock):
        res = self.client.create_hyperparameter(
            algorithm_name='SVM',
            algorithm_params={
                'x': 1,
                'y': 2,
            }
        )

        self.assertResourceResponse(res, 'hyperparameter')

    # Instance types

    @vcr.use_cassette('instance_types/index.yaml')
    def test_get_instance_types(self, sleep_mock):
        res = self.client.get_instance_types()
        self.assertIndexResponse(res, 'instance_type')

    # Organizations

    @vcr.use_cassette('organizations/show.yaml')
    def test_get_organization(self, sleep_mock):
      res = self.client.get_organization(23)
      self.assertResourceResponse(res, 'organization')

    @vcr.use_cassette('organizations/index.yaml')
    def test_get_organizations(self, sleep_mock):
        res = self.client.get_organizations()
        self.assertIndexResponse(res, 'organization')

    @vcr.use_cassette('organizations/create_valid.yaml')
    def test_create_organization_valid(self, sleep_mock):
        res = self.client.create_organization(
            name='my-organization'
        )

        self.assertResourceResponse(res, 'organization')

    @vcr.use_cassette('organizations/update_valid.yaml')
    def test_update_organization_valid(self, sleep_mock):
        res = self.client.update_organization(
            50,
            role_to_assume_arn='arn:aws:iam::529880471834:role/auger-hub-role-alex'
        )

        self.assertResourceResponse(res, 'organization')

    @vcr.use_cassette('organizations/delete_valid.yaml')
    def test_delete_organization_valid(self, sleep_mock):
        res = self.client.delete_organization(50)
        self.assertResourceResponse(res, 'organization')

    # Pipelines

    @vcr.use_cassette('pipelines/show.yaml')
    def test_get_pipeline(self, sleep_mock):
        res = self.client.get_pipeline('c356ff9b6ecc7364')
        self.assertResourceResponse(res, 'pipeline')

    @vcr.use_cassette('pipelines/index.yaml')
    def test_get_pipelines(self, sleep_mock):
        res = self.client.get_pipelines()
        self.assertIndexResponse(res, 'pipeline')

    @vcr.use_cassette('pipelines/create_valid.yaml')
    def test_create_pipeline_valid(self, sleep_mock):
        res = self.client.create_pipeline(trial_id='1231231')
        self.assertResourceResponse(res, 'pipeline')

    @vcr.use_cassette('pipelines/update_valid.yaml')
    def test_update_pipeline_valid(self, sleep_mock):
        res = self.client.update_pipeline(
            'c356ff9b6ecc7364',
            status='packaging'
        )

        self.assertResourceResponse(res, 'pipeline')

    # Pipeline file

    @vcr.use_cassette('pipeline_files/show.yaml')
    def test_get_pipeline_file(self, sleep_mock):
        res = self.client.get_pipeline_file(2)
        self.assertResourceResponse(res, 'pipeline_file')

    @vcr.use_cassette('pipeline_files/index.yaml')
    def test_get_pipeline_files(self, sleep_mock):
        res = self.client.get_pipeline_files()
        self.assertIndexResponse(res, 'pipeline_file')

    @vcr.use_cassette('pipeline_files/create_valid.yaml')
    def test_create_pipeline_file_valid(self, sleep_mock):
        res = self.client.create_pipeline_file(trial_id='3D1E99741D37422')
        self.assertResourceResponse(res, 'pipeline_file')

    # Predictions

    @vcr.use_cassette('predictions/show.yaml')
    def test_get_prediction(self, sleep_mock):
        res = self.client.get_prediction(2)
        self.assertResourceResponse(res, 'prediction')

    @vcr.use_cassette('predictions/index.yaml')
    def test_get_predictions(self, sleep_mock):
        res = self.client.get_predictions()
        self.assertIndexResponse(res, 'prediction')

    @vcr.use_cassette('actuals/create_valid.yaml')
    def test_create_actuals_valid(self, sleep_mock):
        res = self.client.create_actual(
            pipeline_id='46188658d308607a',
            actuals=[{'prediction_id': '1', 'actual': 1},
                     {'prediction_id': '2', 'actual': 1}]
        )

        self.assertResourceEmptyResponse(res, 'actual')

    @vcr.use_cassette('actuals/delete_valid.yaml')
    def test_delete_actuals_valid(self, sleep_mock):
        res = self.client.delete_actuals(
            **{
                'pipeline_id': '118DCF6B1A2A44A',
                'from': '2020-08-10',
                'to': '2020-08-20',
                'with_predictions': True
            }
        )

        self.assertResourceResponse(res, 'cluster_task')

    @vcr.use_cassette('predictions/create_valid_with_nils.yaml')
    def test_create_prediction_valid_with_nils(self, sleep_mock):
        res = self.client.create_prediction(
            pipeline_id='46188658d308607a',
            records=[[1.1, 1.2, 1.3], [2.1, None, None]],
            features=['x1', 'x2', 'x3']
        )

        self.assertResourceResponse(res, 'prediction')

    @vcr.use_cassette('predictions/create_invalid.yaml')
    def test_create_prediction_invalid(self, sleep_mock):
        with self.assertRaises(HubApiClient.InvalidParamsError) as context:
            self.client.create_prediction(
                pipeline_id='46188658d308607a',
                records=[[1.1, 1.2, 1.3], [2.1, 2.2]],
                features=['x1', 'x2', 'x3']
            )

        self.assertIn('each records size should be equal to the features count', str(context.exception))
        self.assertIn('"request_params": {', str(context.exception))

        self.assertIsInstance(context.exception.metadata()['request_params'], dict)
        self.assertEqual(
            json.dumps(context.exception.metadata()['request_params']),
            '{"pipeline_id": "46188658d308607a", "records": [[1.1, 1.2, 1.3], [2.1, 2.2]],'
            ' "features": ["x1", "x2", "x3"], "project_api_token": "****",'
            ' "prediction": {"pipeline_id": "46188658d308607a"}, "project_id": 1}'
        )

    # Response from server in dev mode
    @vcr.use_cassette('predictions/create_invalid_with_nans.yaml')
    def test_create_prediction_invalid_with_nans(self, sleep_mock):
        with self.assertRaises(HubApiClient.FatalApiError) as context:
            self.client.create_prediction(
                pipeline_id='46188658d308607a',
                records=[[1.1, 1.2, 1.3], [2.1, float('NaN'), float('NaN')]],
                features=['x1', 'x2', 'x3']
            )

        self.assertIn('ActionDispatch::Http::Parameters::ParseError', str(context.exception))

    # Response from server in production mode
    @vcr.use_cassette('predictions/create_invalid_with_nan_blank_response.yaml')
    def test_create_prediction_invalid_with_nans_blank_response(self, sleep_mock):
        with self.assertRaises(HubApiClient.FatalApiError) as context:
            self.client.create_prediction(
                pipeline_id='46188658d308607a',
                records=[[1.1, 1.2, 1.3], [2.1, float('NaN'), float('NaN')]],
                features=['x1', 'x2', 'x3']
            )

        self.assertIn('Bad Request', str(context.exception))

    # Prediction groups

    @vcr.use_cassette('prediction_groups/show.yaml')
    def test_get_prediction_group(self, sleep_mock):
        res = self.client.get_prediction_group(7)
        self.assertResourceResponse(res, 'prediction_group')

    @vcr.use_cassette('prediction_groups/index.yaml')
    def test_get_prediction_groups(self, sleep_mock):
        res = self.client.get_prediction_groups()
        self.assertIndexResponse(res, 'prediction_group')

    @vcr.use_cassette('prediction_groups/create_valid.yaml')
    def test_create_prediction_group_valid(self, sleep_mock):
        res = self.client.create_prediction_group(
            pipeline_id='118DCF6B1A2A44A',
            records=[[1.1, 1.2, 1.3, 1.4]],
            features=['sepal_length', 'sepal_length', 'petal_length', 'petal_width']
        )

        self.assertResourceResponse(res, 'prediction_group')

    # Projects

    @vcr.use_cassette('projects/show.yaml')
    def test_get_project(self, sleep_mock):
      res = self.client.get_project(31)
      self.assertResourceResponse(res, 'project')

    @vcr.use_cassette('projects/index.yaml')
    def test_get_projects(self, sleep_mock):
        res = self.client.get_projects()
        self.assertIndexResponse(res, 'project')

    @vcr.use_cassette('projects/create_valid.yaml')
    def test_create_project_valid(self, sleep_mock):
        res = self.client.create_project(
            name='my-project',
            organization_id=23
        )

        self.assertResourceResponse(res, 'project')

    @vcr.use_cassette('projects/update_valid.yaml')
    def test_update_project_valid(self, sleep_mock):
        res = self.client.update_project(
            43,
            default_worker_nodes_count=5,
            default_kubernetes_stack='experimental'
        )

        self.assertResourceResponse(res, 'project')

    @vcr.use_cassette('projects/delete_valid.yaml')
    def test_delete_project_valid(self, sleep_mock):
        res = self.client.delete_project(43)
        self.assertResourceResponse(res, 'project')

    @vcr.use_cassette('projects/get_logs.yaml')
    def test_get_project_logs(self, sleep_mock):
        res = self.client.get_project_logs(31)
        self.assertIsInstance(res, string_type)

    # Pod logs for project

    @vcr.use_cassette('pod_logs/index.yaml')
    def test_get_pod_logs(self, sleep_mock):
        res = self.client.get_pod_logs(project_id=696)
        self.assertIndexResponse(res, 'pod_log')

    @vcr.use_cassette('projects/deploy_project.yaml')
    def test_deploy_project(self, sleep_mock):
        res = self.client.deploy_project(1, worker_type_id=1, workers_count=2)
        self.assertResourceResponse(res, 'project')

    @vcr.use_cassette('projects/undeploy_project.yaml')
    def test_deploy_project(self, sleep_mock):
        res = self.client.undeploy_project(1)
        self.assertResourceResponse(res, 'project')

    # Project files

    @vcr.use_cassette('project_files/show.yaml')
    def test_get_project_file(self, sleep_mock):
      res = self.client.get_project_file(68)
      self.assertResourceResponse(res, 'project_file')

    @vcr.use_cassette('project_files/index.yaml')
    def test_get_project_files(self, sleep_mock):
        res = self.client.get_project_files()
        self.assertIndexResponse(res, 'project_file')

    @vcr.use_cassette('project_files/create_valid.yaml')
    def test_create_project_file_valid(self, sleep_mock):
        res = self.client.create_project_file(
            file_name='my-project_file.csv',
            name='File with data',
            project_id=31,
            url='files/data.csv'
        )

        self.assertResourceResponse(res, 'project_file')

    @vcr.use_cassette('project_files/delete_valid.yaml')
    def test_delete_project_file_valid(self, sleep_mock):
        res = self.client.delete_project_file(69)
        self.assertResourceResponse(res, 'project_file')

    # Project file URLs

    @vcr.use_cassette('project_file_urls/create_valid.yaml')
    def test_create_project_file_url_valid(self, sleep_mock):
        res = self.client.create_project_file_url(
            project_id=1,
            file_path='workspace/projects/mt-test/files/test.csv',
        )

        self.assertEqual(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], dict)
        self.assertTrue(re.match(r'https://[\w\d\-]+.s3.[\w\d\-]+.amazonaws.com', res['data']['url']))
        self.assertIsInstance(res['data']['fields'], dict)
        self.assertEqual(res['data']['fields']['key'], 'workspace/projects/mt-test/files/test.csv')

    @vcr.use_cassette('project_file_urls/create_valid_relative.yaml')
    def test_create_project_file_url_valid_relative(self, sleep_mock):
        res = self.client.create_project_file_url(
            project_id=1,
            file_path='test.csv',
        )

        self.assertEqual(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], dict)
        self.assertTrue(re.match(r'https://[\w\d\-]+.s3.[\w\d\-]+.amazonaws.com', res['data']['url']))
        self.assertIsInstance(res['data']['fields'], dict)
        self.assertEqual(res['data']['fields']['key'], 'workspace/projects/mt-test/files/test.csv')

    @vcr.use_cassette('project_file_urls/show.yaml')
    def test_show_project_file_url(self, sleep_mock):
        res = self.client.get_project_file_url(
            project_id=1,
            file_path='test.csv',
        )

        self.assertEqual(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], dict)
        matcher = r'https://[\w\d\-]+.s3.[\w\d\-]+.amazonaws.com.*files/test.csv?'
        self.assertTrue(re.match(matcher, res['data']['url']))

    # Review alerts

    @vcr.use_cassette('review_alerts/show.yaml')
    def test_get_review_alert(self, sleep_mock):
      res = self.client.get_review_alert(2)
      self.assertResourceResponse(res, 'review_alert')

    @vcr.use_cassette('review_alerts/index.yaml')
    def test_get_review_alerts(self, sleep_mock):
        res = self.client.get_review_alerts()
        self.assertIndexResponse(res, 'review_alert')

    @vcr.use_cassette('review_alerts/create_valid.yaml')
    def test_create_review_alert_valid(self, sleep_mock):
        res = self.client.create_review_alert(
            endpoint_id='ddc968ac-43d5-4aa4-9929-1edba7cefc8f',
            kind='runtime_errors_burst',
            threshold=3,
            sensitivity=48,
            actions='retrain',
        )

        self.assertResourceResponse(res, 'review_alert')

    @vcr.use_cassette('review_alerts/update_valid.yaml')
    def test_update_review_alert_valid(self, sleep_mock):
        res = self.client.update_review_alert(3, threshold=4)
        self.assertResourceResponse(res, 'review_alert')

    @vcr.use_cassette('review_alerts/delete.yaml')
    def test_delete_review_alert_valid(self, sleep_mock):
        res = self.client.delete_review_alert(3)
        self.assertResourceResponse(res, 'review_alert')

    # Review alerts

    @vcr.use_cassette('review_alert_items/show.yaml')
    def test_get_review_alert_item(self, sleep_mock):
      res = self.client.get_review_alert_item(2)
      self.assertResourceResponse(res, 'review_alert_item')

    @vcr.use_cassette('review_alert_items/index.yaml')
    def test_get_review_alert_items(self, sleep_mock):
        res = self.client.get_review_alert_items()
        self.assertIndexResponse(res, 'review_alert_item')

    # Similar trials requests

    @vcr.use_cassette('similar_trials_requests/show.yaml')
    def test_get_similar_trials_request(self, sleep_mock):
        res = self.client.get_similar_trials_request(1)
        self.assertResourceResponse(res, 'similar_trials_request')

    @vcr.use_cassette('similar_trials_requests/create_valid.yaml')
    def test_create_similar_trials_request_valid(self, sleep_mock):
        res = self.client.create_similar_trials_request(
            dataset_manifest_id='fab484c53aec74cf',
            algorithm_name='auger_ml.ensembles.algorithms.VotingAlgorithm',
            algorithm_params_hash='2DD51EA7809C45B',
            limit=5
        )

        self.assertResourceResponse(res, 'similar_trials_request')

    # Status

    @vcr.use_cassette('status/get_status_project_valid.yaml')
    def test_get_status_project_valid(self, sleep_mock):
        res = self.client.get_status(object='Project', id=1)

        self.assertDataResponse(res, {'status': 'undeployed'})

    @vcr.use_cassette('status/get_status_invalid.yaml')
    def test_get_status_invalid(self, sleep_mock):
        with self.assertRaises(HubApiClient.InvalidParamsError) as context:
            res = self.client.get_status(object='User', id=1)

        self.assertInvalidParams(context.exception.metadata(), ['object'])

    # Tokens

    @vcr.use_cassette('tokens/create_valid.yaml')
    def test_create_token_valid(self, sleep_mock):
        res = self.client.create_token(
            email='her@mail.com',
            password='password'
        )

        self.assertDataResponse(res, {'token': string_type, 'confirmation_required': bool})

    @vcr.use_cassette('tokens/create_invalid.yaml')
    def test_create_token_invalid(self, sleep_mock):
        with self.assertRaises(HubApiClient.FatalApiError) as context:
            self.client.create_token(
                email='her@mail.com',
                password='wrong'
            )

        self.assertUnauthenticatedResponse(context.exception.metadata())

    # Trials

    @vcr.use_cassette('trials/show.yaml')
    def test_get_trial(self, sleep_mock):
        res = self.client.get_trial('1231231')
        self.assertResourceResponse(res, 'trial')

    @vcr.use_cassette('trials/index.yaml')
    def test_get_trials(self, sleep_mock):
        res = self.client.get_trials()
        self.assertIndexResponse(res, 'trial')

    @vcr.use_cassette('trials/create.yaml')
    def test_create_trial(self, sleep_mock):
        res = self.client.create_trial(id='bb9887bc5b', refit_data_path='s3://some_new_path.csv')
        self.assertResourceResponse(res, 'trial')

        assert res['data']['id'] != 'bb9887bc5b'
        assert res['data']['raw_data']['refit_data_path'] == 's3://some_new_path.csv'

    @vcr.use_cassette('trials/create.yaml')
    def test_refit_trial(self, sleep_mock):
        res = self.client.refit_trial(id='bb9887bc5b', refit_data_path='s3://some_new_path.csv')
        self.assertResourceResponse(res, 'trial')

        assert res['data']['id'] != 'bb9887bc5b'
        assert res['data']['raw_data']['refit_data_path'] == 's3://some_new_path.csv'

    @vcr.use_cassette('trials/update_one_valid.yaml')
    def test_update_trial_valid(self, sleep_mock):
        res = self.client.update_trial(
            '1231231',
            task_type='classification',
            evaluation_type='fastest one',
            score_name='strict one',
            score_value=99.9,
            hyperparameter={
                'algorithm_name': 'SVM',
                'algorithm_params_hash': 'svm-07.333',
                'algorithm_params': {
                    'x': 1,
                    'y': 2,
                }
            }
        )

        self.assertResourceResponse(res, 'trial')

    @vcr.use_cassette('trials/update_valid.yaml')
    def test_update_trials_valid(self, sleep_mock):
        res = self.client.update_trials(
            experiment_session_id='a2f99b48b6cc5541',
            trials=[
                {
                    'crossValidationFolds': 5,
                    'uid': '3D1E99741D37422',
                    'classification': True,
                    'score': 0.96,
                    'score_name': 'accuracy',
                    'task_type': 'regression',
                    'algorithm_name': 'sklearn.ensemble.ExtraTreesClassifier',
                    'algorithm_params_hash': 'etc-55.777',
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

        self.assertIndexResponse(res, 'trial')

    # Trial searches

    def trial_history(self):
      return [
        {
          'uid': '83D2FE5F2B0A42F',
          'score': 0.43478260869565216,
          'evaluation_time': 0.40130186080932617,
          'algorithm_name': 'sklearn.ensemble.RandomForestClassifier',
          'algorithm_params': {
            'bootstrap': True,
            'max_features': 0.7951475142804721,
            'min_samples_leaf': 13,
            'min_samples_split': 18,
            'n_estimators': 219,
            'n_jobs': 1
          }
        },
        {
          'uid': 'EAD1243A66A7419',
          'score': 0.5869565217391305,
          'ratio': 1.0,
          'evaluation_time': 0.37141990661621094,
          'algorithm_name': 'sklearn.ensemble.RandomForestClassifier',
          'algorithm_params': {
            'bootstrap': True,
            'max_features': 0.5384972025139909,
            'min_samples_leaf': 8,
            'min_samples_split': 12,
            'n_estimators': 188,
            'n_jobs': 1
          }
        }
      ]

    @vcr.use_cassette('trial_searches/show.yaml')
    def test_get_trial_search(self, sleep_mock):
        res = self.client.get_trial_search('1')
        self.assertResourceResponse(res, 'trial_search')

    @vcr.use_cassette('trial_searches/index.yaml')
    def test_get_trial_searches(self, sleep_mock):
        res = self.client.get_trial_searches()
        self.assertIndexResponse(res, 'trial_search')

    @vcr.use_cassette('trial_searches/create_valid.yaml')
    def test_create_trial_search_valid(self, sleep_mock):
        res = self.client.create_trial_search(
            trials_total_count=125,
            search_space={
              "version": 1,
              "optimizers_space": {
                "auger_ml.optimizers.pso_optimizer.PSOOptimizer": {
                  "phig": 0.5,
                  "phip": 0.5,
                  "omega": 0.5
                }
              }
            },
            dataset_metafeatures={
              "ClassEntropy": 1.584962500721156,
              "Dimensionality": 0.02666666666666667,
              "AutoCorrelation": 0.9865771812080537,
              "NumberOfClasses": 3,
            }
          )

        self.assertResourceResponse(res, 'trial_search')

    @vcr.use_cassette('trial_searches/update_valid.yaml')
    def test_update_trial_search_valid(self, sleep_mock):
        res = self.client.update_trial_search(
            id=1,
            trials_limit=12,
            trials_history=self.trial_history()
        )

        self.assertResourceResponse(res, 'trial_search')

    @vcr.use_cassette('trial_searches/update_invalid.yaml')
    def test_update_trial_search_invalid(self, sleep_mock):
        with self.assertRaises(HubApiClient.InvalidParamsError) as context:
          res = self.client.update_trial_search(
              id=1,
              trials_limit=12,
              trials_history=self.trial_history()
          )

        self.assertInvalidParams(context.exception.metadata(), ['id'])

        self.assertIn(
          'trial search can be continued only when previous iteration is done',
          str(context.exception)
        )

    # Warm start requests

    @vcr.use_cassette('warm_start_requests/show.yaml')
    def test_get_warm_start_request(self, sleep_mock):
        res = self.client.get_warm_start_request(1)
        self.assertResourceResponse(res, 'warm_start_request')

    @vcr.use_cassette('warm_start_requests/create_valid.yaml')
    def test_create_warm_start_request_valid(self, sleep_mock):
        res = self.client.create_warm_start_request(
            dataset_manifest_id='100500',
            score_name='logloss'
        )

        self.assertResourceResponse(res, 'warm_start_request')

    # Optimizers srvice

    # For `SECRET_KEY=strong-secret`
    def build_hub_client_for_optimizer(self, optimizers_url='http://localhost:7777', token=None):
        if not token:
            token = 'eyJhbGciOiJIUzI1NiJ9.eyJ4IjoxfQ.NLc1yhn2PDZhJaWTI2dtHkHzn2r8cND1MwiwrVtNlx0'

        return HubApiClient(
            hub_app_url='http://localhost:5000',
            optimizers_url=optimizers_url,
            retries_count=1,
            hub_project_api_token=token
        )

    # POST /next_trials

    def test_get_next_trials_missing_optimizers_url(self, sleep_mock):
        client = self.build_hub_client_for_optimizer(optimizers_url=None)

        with self.assertRaises(HubApiClient.MissingParamError) as context:
            client.get_next_trials({'x': 1})

        self.assertEqual(str(context.exception), 'pass optimizers_url in HubApiClient constructor')

    def test_get_next_trials_blank_optimizers_url(self, sleep_mock):
        client = self.build_hub_client_for_optimizer(optimizers_url='')

        with self.assertRaises(HubApiClient.MissingParamError) as context:
            client.get_next_trials({'x': 1})

        self.assertEqual(str(context.exception), 'pass optimizers_url in HubApiClient constructor')

    @vcr.use_cassette('optimizers_service/get_next_trials_invalid_token.yaml')
    def test_get_next_trials_invalid_token(self, sleep_mock):
        client = self.build_hub_client_for_optimizer(token='wrong')

        with self.assertRaises(HubApiClient.FatalApiError) as context:
            client.get_next_trials({'x': 1})

        self.assertUnauthenticatedResponse(context.exception.metadata())

    @vcr.use_cassette('optimizers_service/get_next_trials_valid.yaml')
    def test_get_next_trials_valid(self, sleep_mock):
        client = self.build_hub_client_for_optimizer()

        with open('tests/fixtures/get_next_trials_payload.json', 'r') as file:
            res = client.get_next_trials(json.loads(file.read()))

    @vcr.use_cassette('optimizers_service/get_next_trials_invalid_request.yaml')
    def test_get_next_trials_invalid_request(self, sleep_mock):
        client = self.build_hub_client_for_optimizer()

        with self.assertRaises(HubApiClient.InvalidParamsError) as context:
            res = client.get_next_trials({'x': 'some'})

        self.assertInvalidParams(context.exception.metadata(), ['optimizer_name'])

    # POST /v2/next_trials

    @vcr.use_cassette('optimizers_service/get_next_trials_v2_valid.yaml')
    def test_get_next_trials_v2_valid(self, sleep_mock):
        client = self.build_hub_client_for_optimizer()

        with open('tests/fixtures/get_next_trials_v2_payload.json', 'r') as file:
            res = client.get_next_trials_v2(json.loads(file.read()))

    # POST /fte
    @vcr.use_cassette('optimizers_service/get_fte_valid.yaml')
    def test_get_fte_valid(self, sleep_mock):
        client = self.build_hub_client_for_optimizer()

        payload = {
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
        }

        res = client.get_fte(payload)

        self.assertIsInstance(res['data']['estimated_time'], float)

    @vcr.use_cassette('optimizers_service/get_fte_invalid.yaml')
    def test_get_fte_invalid(self, sleep_mock):
        client = self.build_hub_client_for_optimizer()

        payload = {
            'alg_name': "sklearn.ensemble.RandomForestClassifier",
            'ncols': 100,
            'nrows': 10000
        }

        with self.assertRaises(HubApiClient.InvalidParamsError) as context:
            res = client.get_fte(payload)

        self.assertInvalidParams(context.exception.metadata(), ['alg_params'])
