import json
import re
import requests
import time

try:
    # Python 3
    from urllib.parse import urljoin
    from json.decoder import JSONDecodeError
except ImportError:
    # Python 2
    from urlparse import urljoin

    # Stub class to unify handler code
    class JSONDecodeError(Exception):
        pass

from requests.exceptions import ConnectionError

class HubApiClient:
    class BaseError(Exception):
        def metadata(self):
            return self.args[1]

    # Means that consumer code can't do nothing with this error
    # Only changing of comnsumer source code or config parameters can help
    class FatalApiError(BaseError):
        pass

    # Wrong input, consumer should fix input values
    class InvalidParamsError(BaseError):
        pass

    # Temporary network issue, retry can help
    class RetryableApiError(BaseError):
        pass

    class MissingParamError(BaseError):
        pass

    API_SCHEMA = {
        'cluster': {
            'actions': ['index', 'show', 'create', 'delete']
        },
        'cluster_task': {
            'actions': ['index', 'show', 'create']
        },
        'dataset_manifest': {
            'actions': ['index', 'show', 'create', 'update']
        },
        'experiment': {
            'actions': ['index', 'show', 'create', 'update', 'delete']
        },
        'experiment_session': {
            'actions': ['index', 'show', 'create', 'update'],
        },
        'hyperparameter': {
            'actions': ['index', 'show', 'create']
        },
        'instance_type': {
            'actions': ['index']
        },
        'organization': {
            'actions': ['index', 'show', 'create', 'update', 'delete']
        },
        'pipeline': {
            'actions': ['index', 'show', 'create', 'update']
        },
        'pipeline_file': {
            'actions': ['index', 'show', 'create', 'update']
        },
        'prediction': {
            'actions': ['index', 'show', 'create']
        },
        'project': {
            'actions': ['index', 'show', 'create', 'update', 'delete']
        },
        'project_file': {
            'actions': ['index', 'show', 'create', 'delete']
        },
        'similar_trials_request': {
            'actions': ['show', 'create']
        },
        'token': {
            'actions': ['create']
        },
        'trial': {
            'actions': ['index', 'show', 'update']
        },
        'warm_start_request': {
            'actions': ['show', 'create']
        }
    }

    API_PREFIX = '/api/v1'

    def __init__(self, **config):
        self.base_url = config['hub_app_url']
        self.optimizers_url = config.get('optimizers_url', None)
        self.token = config.get('token', None)
        self.system_token = config.get('hub_system_token', None)
        self.cluster_api_token = config.get('hub_cluster_api_token', None)
        self.project_api_token = config.get('hub_project_api_token', None)
        self.retries_count = config.get('retries_count', 5)
        self.retry_wait_seconds = config.get('retry_wait_seconds', 5)
        self.headers = { 'Content-Type': 'application/json' }

        self.define_actions()

    def full_path(self, relative_path, base_url):
        return urljoin(base_url, relative_path)

    def extract_plain_text(self, html):
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html)

    def tokens_payload(self):
        if self.project_api_token:
            return { 'project_api_token': self.project_api_token }
        elif self.cluster_api_token:
            return { 'cluster_api_token': self.cluster_api_token }
        elif self.token:
            return { 'token': self.token }
        elif self.system_token:
            return { 'system_token': self.system_token }
        else:
            return {}

    def request(self, method_name, path, base_url, payload={}):
        try:
            method = getattr(requests, method_name)

            params = payload.copy()
            params.update(self.tokens_payload())

            return method(self.full_path(relative_path=path, base_url=base_url), json=params, headers=self.headers)
        except ConnectionError as e:
            raise self.RetryableApiError(str(e))

    def handle_response(self, res, plain_text=False):
        if plain_text:
            reponse = res.text
            meta = {}
        else:
            try:
                reponse = res.json()
                meta = reponse.get('meta')
            except (JSONDecodeError, ValueError):
                response = res.text
                meta = {}

        if res.status_code == 200:
            return reponse
        elif res.status_code == 400:
            # Invalid input data, we can't do anyting, consumer should fix source code
            raise self.InvalidParamsError(self.format_response(res), meta)
        elif res.status_code == 401 or res.status_code == 403 or res.status_code == 404 or res.status_code == 500:
            # Invalid token or error in source code, we can't do anyting raise error
            raise self.FatalApiError(self.format_response(res), meta)
        else:
            # In case of another error we can retry
            raise self.RetryableApiError(self.format_response(res), meta)

    def format_api_error(self, error):
        return '{param} {message}'.format(
            param=error['error_param'],
            message=error['message']
        )

    def format_response(self, res):
        try:
            if res.status_code == 400:
                errors = res.json()['meta']['errors']
                return ', '.join(map(lambda error: self.format_api_error(error), errors))
            else:
                return 'status: {}, body: {}'.format(res.status_code, self.extract_plain_text(res.text))
        except (JSONDecodeError, ValueError) as e:
            raise self.FatalApiError(self.extract_plain_text(res.text))

    def make_and_handle_request(self, method_name, path, base_url=None, payload={}, retries_left=5, plain_text=False):
        if not base_url:
            base_url = self.base_url

        try:
            res = self.request(method_name, path, base_url, payload)
            return self.handle_response(res, plain_text=plain_text)
        except self.RetryableApiError as e:
            if retries_left > 0:
                time.sleep(self.retry_wait_seconds)
                return self.make_and_handle_request(method_name, path, base_url, payload, retries_left-1)
            else:
                raise e

    def get(self, path, payload = {}):
        return self.make_and_handle_request('get', path, payload=payload, retries_left=self.retries_count)


    def get_paginated_response(self, full_path, limit=50, offset=0, **kwargs):
        args = { 'limit': limit, 'offset': offset }
        args.update(kwargs)
        return self.get(full_path, args)

    def iterate_all_resource_pages(self, method_name, handler, **kwargs):
        offset = 0
        while True:
            method = getattr(self, method_name)

            args = { 'offset': offset }
            args.update(kwargs)

            res = method(**args)

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
            return '{api_prefix}/{resource_name}s'.format(
                api_prefix=self.API_PREFIX,
                resource_name=resource_name
            )

    def define_actions(self):
        for resource_name, options in self.API_SCHEMA.items():
            parent_resource_name = options.get('parent_resource', None)
            path = self.build_full_resource_path(resource_name, parent_resource_name)

            for action_name in options['actions']:
                self.define_action(action_name, path, resource_name, parent_resource_name)

    def format_full_resource_path(self, path_template, parent_resource_name, kwargs):
        if parent_resource_name:
            parent_id_key = parent_resource_name + '_id'
            parent_id = kwargs.get(parent_id_key, None)
            if parent_id:
                return path_template.format(parent_id=parent_id)
            else:
                raise self.MissingParamError(
                    '{name} parameter is required'.format(name=parent_id_key),
                    res.json().get('meta')
                )
        elif not parent_resource_name:
            return path_template
        else:
            raise self.FatalApiError('missing parent_id parameter')

    def define_action(self, action_name, path_template, resource_name, parent_resource_name):
        if action_name == 'index':
            index_proc_name = 'get_{resource_name}s'.format(resource_name=resource_name)
            iterate_proc_name = 'iterate_all_{resource_name}s'.format(resource_name=resource_name)

            def index(self, **kwargs):
                path = self.format_full_resource_path(path_template, parent_resource_name, kwargs)
                return self.get_paginated_response(path, **kwargs)

            def iterate(self, handler, **kwargs):
                return self.iterate_all_resource_pages(index_proc_name, handler, **kwargs)

            setattr(self.__class__, index_proc_name, index)
            setattr(self.__class__, iterate_proc_name, iterate)

        elif action_name == 'show':
            show_proc_name = 'get_{resource_name}'.format(resource_name=resource_name)

            def show(self, id, **kwargs):
                path = self.format_full_resource_path(path_template, parent_resource_name, kwargs)
                return self.make_and_handle_request('get', '{path}/{id}'.format(path=path, id=id))

            setattr(self.__class__, show_proc_name, show)

        elif action_name == 'create':
            create_proc_name = 'create_{resource_name}'.format(resource_name=resource_name)

            def create(self, **kwargs):
                path = self.format_full_resource_path(path_template, parent_resource_name, kwargs)
                return self.make_and_handle_request('post', path, payload=kwargs)

            setattr(self.__class__, create_proc_name, create)

        elif action_name == 'update':
            update_proc_name = 'update_{resource_name}'.format(resource_name=resource_name)

            def update(self, id, **kwargs):
                path = self.format_full_resource_path(path_template, parent_resource_name, kwargs)
                if id:
                    path='{path}/{id}'.format(path=path, id=id)
                return self.make_and_handle_request('patch', path, payload=kwargs)

            setattr(self.__class__, update_proc_name, update)
        elif action_name == 'delete':
            delete_proc_name = 'delete_{resource_name}'.format(resource_name=resource_name)

            def delete(self, id):
                path = self.format_full_resource_path(path_template, parent_resource_name, {})
                return self.make_and_handle_request('delete', '{path}/{id}'.format(path=path, id=id))

            setattr(self.__class__, delete_proc_name, delete)
        else:
            raise 'Unsupported REST action `{name}`'.format(name=action_name)


    # Deviation, not pure RESTfull endpoint, updates a bunch of trials for project run
    def update_trials(self, **kwargs):
        return self.update_trial(id=None, **kwargs)

    def get_project_logs(self, id, **kwargs):
        path = '{api_prefix}/projects/{id}/logs'.format(api_prefix=self.API_PREFIX, id=id)
        return self.make_and_handle_request('get', path, plain_text=True)

    # Optimizers service client
    def get_next_trials(self, payload={}):
        if self.optimizers_url:
            path = '/next_trials'
            return self.make_and_handle_request('post', path, payload=payload, base_url=self.optimizers_url)
        else:
            raise self.MissingParamError('pass optimizers_url in HubApiClient constructor')
