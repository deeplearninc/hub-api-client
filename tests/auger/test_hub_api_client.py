import unittest
import random
from mock import patch

from auger.hub_api_client import HubApiClient
from tests.vcr_helper import vcr

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

    # Pipelines

    @vcr.use_cassette('pipelines/show.yaml')
    def test_get_pipeline(self, sleep_mock):
        res = self.client.get_pipeline('37fec5a5bfa9f3', experiment_session_id='1bf484f7305779')
        self.assertResourceResponse(res, 'pipeline')

    @vcr.use_cassette('pipelines/index.yaml')
    def test_get_pipelines(self, sleep_mock):
        res = self.client.get_pipelines(experiment_session_id='1bf484f7305779')
        self.assertIndexResponse(res, 'pipeline')

    @vcr.use_cassette('pipelines/create_valid.yaml')
    def test_create_pipeline_valid(self, sleep_mock):
        res = self.client.create_pipeline(
            experiment_session_id='1bf484f7305779',
            id='pipeline-123',
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

        self.assertResourceResponse(res, 'pipeline')

    @vcr.use_cassette('pipelines/update_valid.yaml')
    def test_create_pipeline_valid(self, sleep_mock):
        res = self.client.update_pipeline(
            'pipeline-123',
            experiment_session_id='1bf484f7305779',
            status='packaging'
        )

        self.assertResourceResponse(res, 'pipeline')

    # Trials

    @vcr.use_cassette('trials/show.yaml')
    def test_get_trial(self, sleep_mock):
        res = self.client.get_trial('2c9f4cd18e', experiment_session_id='1bf484f7305779')
        self.assertResourceResponse(res, 'trial')

    @vcr.use_cassette('trials/index.yaml')
    def test_get_trials(self, sleep_mock):
        res = self.client.get_trials(experiment_session_id='1bf484f7305779')
        self.assertIndexResponse(res, 'trial')

    @vcr.use_cassette('trials/update_one_valid.yaml')
    def test_update_trial_valid(self, sleep_mock):
        res = self.client.update_trial(
            '2c9f4cd18e',
            experiment_session_id='1bf484f7305779',
            task_type='classification',
            evaluation_type='fastest one',
            score_name='strict one',
            score_value=99.9,
            hyperparameter={
                'algorithm_name': 'SVM',
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
            experiment_session_id='1bf484f7305779',
            trials=[
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

        self.assertIndexResponse(res, 'trial')

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
