import re
import requests
import time
import urllib.parse

from requests.exceptions import ConnectionError

class HubApiClient:
    # Means that consumer code can't do nothing with this error
    # Only changing of comnsumer source code or config parameters can help
    class FatalApiError(Exception):
        pass

    # Wrong input, consumer should fix input values
    class InvalidParamsError(Exception):
        def metadata(self):
            return self.args[1]

    # Temporary network issue, retry can help
    class RetryableApiError(Exception):
        pass

    API_SCHEMA = {
        'dataset_manifest': {
            'actions': ['index', 'show', 'create']
        },
        'hyperparameter': {
            'actions': ['index', 'show', 'create']
        },
        'project_run': {
            'actions': ['index', 'show', 'create', 'update'],
        },
        'pipeline': {
            'actions': ['index', 'show', 'create', 'update'],
            'parent_resource': 'project_run'
        },
        'trial': {
            'actions': ['index', 'show', 'update'],
            'parent_resource': 'project_run'
        }
    }

    def __init__(self, **config):
        self.host = config['hub_app_host']
        self.system_token = config.get('hub_system_token', None)
        self.cluster_api_token = config.get('hub_cluster_api_token', None)
        self.project_api_token = config.get('hub_project_api_token', None)
        self.retries_count = config.get('retries_count', 5)
        self.retry_wait_seconds = config.get('retry_wait_seconds', 5)
        self.headers = { 'Content-type': 'application/json' }

        self.define_actions()

    def full_path(self, relative_path):
        return urllib.parse.urljoin(self.host, relative_path)

    def extract_plain_text(self, html):
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html)

    def tokens_payload(self):
        if self.project_api_token:
            return { 'project_api_token': self.project_api_token }
        elif self.cluster_api_token:
            return { 'cluster_api_token': self.cluster_api_token }
        elif self.system_token:
            return { 'system_token': self.system_token }
        else:
            raise self.FatalApiError('expect any token to be provided in configuration')

    def request(self, method_name, path, payload={}):
        try:
            method = getattr(requests, method_name)
            params = { **payload, **self.tokens_payload() }
            return method(self.full_path(path), json=params, headers=self.headers)
        except ConnectionError as e:
            raise self.RetryableApiError(str(e))

    def handle_response(self, res):
        if res.status_code == 200:
            return res.json()
        elif res.status_code == 400:
            # Invalid input data, we can't do anyting, consumer should fix source code
            raise self.InvalidParamsError(self.format_response(res), res.json()['meta'])
        elif res.status_code == 401 or res.status_code == 403 or res.status_code == 404 or res.status_code == 500:
            # Invalid token or error in source code, we can't do anyting raise error
            raise self.FatalApiError(self.format_response(res))
        else:
            # In case of another error we can retry
            raise self.RetryableApiError(self.format_response(res))

    def format_api_error(self, error):
        return '{param} {message}'.format(
            param=error['error_param'],
            message=error['message']
        )

    def format_response(self, res):
        if res.status_code == 400:
            errors = res.json()['meta']['errors']
            return ', '.join(map(lambda error: self.format_api_error(error), errors))
        else:
            return 'status: {}, body: {}'.format(res.status_code, self.extract_plain_text(res.text))

    def make_and_handle_request(self, method_name, path, payload={}, retries_left=5):
        try:
            res = self.request(method_name, path, payload)
            return self.handle_response(res)
        except self.RetryableApiError as e:
            if retries_left > 0:
                time.sleep(self.retry_wait_seconds)
                return self.make_and_handle_request(method_name, path, payload, retries_left-1)
            else:
                raise e

    def get(self, path, payload = {}):
        return self.make_and_handle_request('get', path, payload, self.retries_count)


    def get_paginated_response(self, full_path, limit=50, offset=0):
        return self.get(full_path, { 'limit': limit, 'offset': offset })

    def iterate_all_resource_pages(self, method_name, handler, **kwargs):
        offset = 0
        while True:
            method = getattr(self, method_name)
            res = method(**{ 'offset': offset, **kwargs })

            for item in res['data']:
                handler(item)

            count = res['meta']['pagination']['count']

            if count > 0:
                offset += count
            else:
                break;

    def build_full_resource_path(self, resource_name, parent_resource_name):
        if parent_resource_name:
            return '/api/v1/{parent_resource_name}s/{{parent_id}}/{resource_name}s'.format(
                resource_name=resource_name,
                parent_resource_name=parent_resource_name,
            )
        else:
            return '/api/v1/{resource_name}s'.format(resource_name=resource_name)

    def define_actions(self):
        for resource_name, options in self.API_SCHEMA.items():
            parent_resource_name = options.get('parent_resource', None)
            path = self.build_full_resource_path(resource_name, parent_resource_name)

            for action_name in options['actions']:
                self.define_action(action_name, path, resource_name, parent_resource_name)

    def format_full_resource_path(self, path_template, parent_resource_name, parent_id):
        if parent_resource_name and parent_id:
            return path_template.format(parent_id=parent_id)
        elif not parent_resource_name:
            return path_template
        else:
            raise self.FatalApiError('missing parent_id parameter')

    def define_action(self, action_name, path_template, resource_name, parent_resource_name):
        if action_name == 'index':
            index_proc_name = 'get_{resource_name}s'.format(resource_name=resource_name)
            iterate_proc_name = 'iterate_all_{resource_name}s'.format(resource_name=resource_name)

            def index(self, parent_id=None, **kwargs):
                path = self.format_full_resource_path(path_template, parent_resource_name, parent_id)
                return self.get_paginated_response(path, **kwargs)

            def iterate(self, handler, **kwargs):
                return self.iterate_all_resource_pages(index_proc_name, handler, **kwargs)

            setattr(self.__class__, index_proc_name, index)
            setattr(self.__class__, iterate_proc_name, iterate)

        elif action_name == 'show':
            show_proc_name = 'get_{resource_name}'.format(resource_name=resource_name)

            def show(self, id, parent_id=None):
                path = self.format_full_resource_path(path_template, parent_resource_name, parent_id)
                return self.make_and_handle_request('get', '{path}/{id}'.format(path=path, id=id))

            setattr(self.__class__, show_proc_name, show)

        elif action_name == 'create':
            create_proc_name = 'create_{resource_name}'.format(resource_name=resource_name)

            def create(self, parent_id=None, **kwargs):
                path = self.format_full_resource_path(path_template, parent_resource_name, parent_id)
                return self.make_and_handle_request('post', path, kwargs)

            setattr(self.__class__, create_proc_name, create)

        elif action_name == 'update':
            update_proc_name = 'update_{resource_name}'.format(resource_name=resource_name)

            def update(self, id, parent_id=None, **kwargs):
                path = self.format_full_resource_path(path_template, parent_resource_name, parent_id)
                if id:
                    path='{path}/{id}'.format(path=path, id=id)
                return self.make_and_handle_request('patch', path, kwargs)

            setattr(self.__class__, update_proc_name, update)
        else:
            raise 'Unsupported REST action `{name}`'.format(name=action_name)


    # Deviation, not pure RESTfull endpoint, updates a bunch of trials for project run
    def update_trials(self, parent_id, **kwargs):
        return self.update_trial(id=None, parent_id=parent_id, **kwargs)
