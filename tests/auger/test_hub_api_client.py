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

    # Project runs

    @vcr.use_cassette('project_runs/show.yaml')
    def test_get_project_run(self, sleep_mock):
        res = self.client.get_project_run(1)
        self.assertResourceResponse(res, 'project_run')

    @vcr.use_cassette('project_runs/index.yaml')
    def test_get_project_runs(self, sleep_mock):
        res = self.client.get_project_runs()
        self.assertIndexResponse(res, 'project_run')

    @vcr.use_cassette('project_runs/create_malformed_json.yaml')
    def test_create_project_run_malformed_json(self, sleep_mock):
        with self.assertRaises(HubApiClient.FatalApiError) as context:
            self.client.create_project_run(
                notebook_uid='afaf-dfgdfhg-gdfgdg',
                status='running',
                leaderbord={'a1': 1, 'a2': 2},
                model_settings={'x': float('inf')},
                message='Some sort of message'
            )

    @vcr.use_cassette('project_runs/create_valid.yaml')
    def test_create_project_run_valid(self, sleep_mock):
        res = self.client.create_project_run(
            notebook_uid='afaf-dfgdfhg-gdfgdg',
            status='running',
            leaderbord={'a1': 1, 'a2': 2},
            model_settings={'x': 1, 'y': 2},
            message='Some sort of message'
        )

        self.assertResourceResponse(res, 'project_run')

    @vcr.use_cassette('project_runs/update_valid.yaml')
    def test_update_project_run_valid(self, sleep_mock):
        res = self.client.update_project_run(4, status='completed')
        self.assertResourceResponse(res, 'project_run')

    # Pipelines

    @vcr.use_cassette('pipelines/show.yaml')
    def test_get_pipeline(self, sleep_mock):
        res = self.client.get_pipeline(12313, project_run_id=1)
        self.assertResourceResponse(res, 'pipeline')

    @vcr.use_cassette('pipelines/index.yaml')
    def test_get_pipelines(self, sleep_mock):
        res = self.client.get_pipelines(project_run_id=1)
        self.assertIndexResponse(res, 'pipeline')

    @vcr.use_cassette('pipelines/create_valid.yaml')
    def test_create_pipeline_valid(self, sleep_mock):
        res = self.client.create_pipeline(
            project_run_id=1,
            id='pipeline-123',
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

        self.assertResourceResponse(res, 'pipeline')

    @vcr.use_cassette('pipelines/update_valid.yaml')
    def test_create_pipeline_valid(self, sleep_mock):
        res = self.client.update_pipeline('pipeline-123', project_run_id=1, status='packaging')
        self.assertResourceResponse(res, 'pipeline')

    # Trials

    @vcr.use_cassette('trials/show.yaml')
    def test_get_trial(self, sleep_mock):
        res = self.client.get_trial(3, project_run_id=1)
        self.assertResourceResponse(res, 'trial')

    @vcr.use_cassette('trials/index.yaml')
    def test_get_trials(self, sleep_mock):
        res = self.client.get_trials(project_run_id=1)
        self.assertIndexResponse(res, 'trial')

    @vcr.use_cassette('trials/update_valid.yaml')
    def test_update_trials_valid(self, sleep_mock):
        res = self.client.update_trials(
            project_run_id=1,
            dataset_manifest_id=100500,
            trials=[
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
