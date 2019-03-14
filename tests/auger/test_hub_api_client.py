import unittest
import random
import sys
from mock import patch

from auger.hub_api_client import HubApiClient
from tests.vcr_helper import vcr

if sys.version_info[0] >= 3:
    string_type = str
else:
    string_type = unicode

@patch('time.sleep', return_value=None)
class TestHubApiClient(unittest.TestCase):
    def setUp(self):
        self.hub_project_api_token = '410befdcd606f602c20e5140b94909aeff27800a86459ceb1fc97b7e09bce57b'
        self.client = HubApiClient(
          hub_app_url='http://localhost:5000',
          retries_count=1,
          hub_project_api_token=self.hub_project_api_token
        )

    def assertInvalidParams(self, metadata, expected_params):
        actual_params = list(map(lambda error: error['error_param'], metadata['errors']))
        self.assertEquals(actual_params, expected_params)

    def assertIndexResponse(self, res, expected_object):
        self.assertEquals(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], list)
        self.assertTrue(len(res['data']) > 0)
        self.assertEquals(res['data'][0]['object'], expected_object)

    def assertResourceResponse(self, res, expected_object):
        self.assertEquals(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], dict)
        self.assertEquals(res['data']['object'], expected_object)

    def assertDataResponse(self, res, expected_keys):
        self.assertEquals(res['meta']['status'], 200)
        self.assertIsInstance(res['data'], dict)
        for expected_key in expected_keys:
            expected_type = expected_keys[expected_key]
            self.assertIsInstance(res['data'][expected_key], expected_type)

    def assertUnauthenticatedResponse(self, metadata):
        self.assertEquals(metadata['status'], 401)
        error = metadata['errors'][0]
        self.assertEquals(error['error_type'], 'unauthenticated')
        self.assertIsInstance(error['message'], string_type)

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
          lambda item: self.assertEquals(item['object'], 'dataset_manifest'),
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
