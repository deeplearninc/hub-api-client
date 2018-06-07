import unittest
import random
from mock import patch

# from services.config import Config
from auger.hub_api_client import HubApiClient

@patch('time.sleep', return_value=None)
class TestHubApiClient(unittest.TestCase):
    def setUp(self):
        self.hub_project_api_token = '481da66630fe89649b5450be8c7cb7c5'
        self.client = HubApiClient(**{
          'hub_app_host': 'http://localhost:5000',
          'retries_count': 1,
          'hub_project_api_token': self.hub_project_api_token
        })

    # Dataset manifests

    def test_get_dataset_manifests(self, sleep_mock):
        res = self.client.get_dataset_manifests()
        print(res)

    def test_iterate_all_dataset_manifests(self, sleep_mock):
        self.client.iterate_all_dataset_manifests(lambda item: print(item))

    def test_create_dataset_manifest_invalid(self, sleep_mock):
        with self.assertRaises(HubApiClient.InvalidParamsError) as context:
            self.client.create_dataset_manifest(name='test')

        self.assertTrue('is required' in str(context.exception))

    def test_create_dataset_manifest_valid(self, sleep_mock):
        res = self.client.create_dataset_manifest(
            id=100500,
            name='test',
            statistics={'x': 1, 'y': 2}
        )
        print(res)

    def test_get_dataset_manifest(self, sleep_mock):
      res = self.client.get_dataset_manifest(100500)
      print(res)

    def test_get_project_runs(self, sleep_mock):
        res = self.client.get_project_runs()
        print(res)


    def test_get_project_run(self, sleep_mock):
        res = self.client.get_project_run(1)
        print(res)

    def test_get_pipelines(self, sleep_mock):
        res = self.client.get_pipelines(parent_id=1)
        print(res)

    def test_get_trials(self, sleep_mock):
        res = self.client.get_trials(parent_id=1)
        print(res)

    def test_update_trials(self, sleep_mock):
        params = {
        'dataset_manifest_id': 2,
        'trials': [
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
        }

        res = self.client.update_trials(parent_id=1, **params)
        print(res)
