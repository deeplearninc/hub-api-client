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
        self.hub_project_api_token = '410befdcd606f602c20e5140b94909aeff27800a86459ceb1fc97b7e09bce57b'

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

    # Clusters

    @vcr.use_cassette('clusters/show.yaml')
    def test_get_cluster(self, sleep_mock):
      res = self.client.get_cluster(127)
      self.assertResourceResponse(res, 'cluster')

    @vcr.use_cassette('clusters/index.yaml')
    def test_get_clusters(self, sleep_mock):
        res = self.client.get_clusters()
        self.assertIndexResponse(res, 'cluster')

    @vcr.use_cassette('clusters/create_valid.yaml')
    def test_create_cluster_valid(self, sleep_mock):
        res = self.client.create_cluster(
            name='my-cluster',
            organization_id=23,
            project_id=31
        )

        self.assertResourceResponse(res, 'cluster')

    @vcr.use_cassette('clusters/delete_valid.yaml')
    def test_delete_cluster_valid(self, sleep_mock):
        res = self.client.delete_cluster(340)
        self.assertResourceResponse(res, 'cluster')

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

    @vcr.use_cassette('predictions/create_valid.yaml')
    def test_create_prediction_valid(self, sleep_mock):
        res = self.client.create_prediction(
            pipeline_id='46188658d308607a',
            records=[[1.1, 1.2, 1.3], [2.1, 2.2, 2.3]],
            features=['x1', 'x2', 'x3']
        )

        self.assertResourceResponse(res, 'prediction')

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
