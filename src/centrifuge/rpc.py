# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import six
from bson import ObjectId
from tornado.escape import json_encode
from tornado.gen import Task, coroutine, Return

from . import utils


state = None


@coroutine
def broadcast_event(event, app, allowed_categories):
    """
    Publish event into PUB socket stream
    """
    project_id = event['project_id']
    category_id = event['category_id']
    category_name = event['category']

    message = json_encode(event)

    if allowed_categories[category_name]['publish_to_admins']:
        # send to project channel (only for admin use)
        channel = create_project_channel_name(project_id)
        publish(app.pub_stream, channel, message)

    # send to event channel
    channel = create_channel_name(
        project_id, category_id, event['channel']
    )
    publish(app.pub_stream, channel, message)

    raise Return((True, None))


@coroutine
def prepare_event(application, project, allowed_categories, params):
    """
    Prepare event before actual broadcasting.
    """
    opts = application.settings['options']

    category_name = params.get('category')
    channel = params.get('channel')
    event_data = params.get('data')

    # clean html if necessary
    html = opts.get('html', {})
    clean = html.get('clean', False)
    if clean:
        allowed_domains = html.get('allowed_domains', ())
        for key, value in six.iteritems(event_data):
            if not isinstance(value, six.string_types):
                continue
            cleaned_value = utils.clean_html(
                value, host_whitelist=allowed_domains
            )
            event_data[key] = cleaned_value

    category = allowed_categories.get(category_name, None)
    if not category:
        raise Return(("category not found", None))

    event = {
        '_id': str(ObjectId()),
        'project': project['_id'],
        'category': category['_id'],
        'channel': channel,
        'data': event_data,
    }

    to_process = {
        'project_id': project['_id'],
        'project': project['name'],
        'category_id': category['_id'],
        'category': category['name'],
        'event_id': event['_id'],
        'channel': event['channel'],
        'data': event['data']
    }

    raise Return((to_process, None))


@coroutine
def process_broadcast(application, project, allowed_categories, params):

    result, error = yield prepare_event(
        application, project, allowed_categories, params
    )
    if error:
        raise Return((None, 'internal server error'))

    if isinstance(result, dict):
        # event stored successfully and we can make callbacks
        result, error = yield broadcast_event(
            result, application, allowed_categories
        )

        # process custom callbacks, and let it fail in case of any error
        jobs = [Task(cb, result, application) for cb in application.event_callbacks]
        yield jobs

    else:
        # result is error description
        raise Return((None, result))

    raise Return((True, None))


@coroutine
def process_call(application, project, method, params):
    """
    Process request from project's administrators - broadcast new
    event or share control message between all tornado instances
    running.
    """
    assert isinstance(project, dict)

    if method == "broadcast":

        project_categories, error = yield state.get_project_categories(project)
        if error:
            raise Return((None, error))

        allowed_categories = dict((x['name'], x) for x in project_categories)

        result, error = yield process_broadcast(
            application, project, allowed_categories, params
        )
    else:
        params["project"] = project
        to_publish = {
            "method": method,
            "params": params
        }
        publish(
            application.pub_stream,
            CONTROL_CHANNEL_NAME,
            json_encode(to_publish)
        )
        result, error = True, None

    raise Return((result, error))