# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import six
from bson import ObjectId
from tornado.escape import json_encode, json_decode
from tornado.gen import Task, coroutine, Return

import zmq

from . import utils


state = None


CHANNEL_PREFIX = 'centrifuge'


CHANNEL_NAME_SEPARATOR = ':'


CHANNEL_DATA_SEPARATOR = ' '


CHANNEL_SUFFIX = '>>>'


def publish(stream, channel, message):
    """
    Publish message into channel of stream.
    """
    to_publish = "{0}{1}{2}".format(
        channel, CHANNEL_DATA_SEPARATOR, message
    )
    stream.send_unicode(to_publish)


def create_channel_name(project_id, category_id, channel):
    return str(CHANNEL_NAME_SEPARATOR.join([
        CHANNEL_PREFIX,
        'event',
        project_id,
        category_id,
        channel,
        CHANNEL_SUFFIX
    ]))


def parse_channel_name(channel):
    project_id, category_id, channel = channel.split(
        CHANNEL_NAME_SEPARATOR, 5
    )[2:5]
    return project_id, category_id, channel


def create_project_channel_name(project_id):
    return str(CHANNEL_NAME_SEPARATOR.join([
        CHANNEL_PREFIX,
        'project',
        project_id,
        CHANNEL_SUFFIX
    ]))


def parse_project_channel_name(channel):
    project_id = channel.split(CHANNEL_NAME_SEPARATOR, 3)[2]
    return project_id


def create_control_channel_name():
    return str(CHANNEL_NAME_SEPARATOR.join([
        CHANNEL_PREFIX,
        'control',
        CHANNEL_SUFFIX
    ]))


CONTROL_CHANNEL_NAME = create_control_channel_name()


@coroutine
def handle_control_message(application, message):
    """
    Handle special control message.
    """
    # extract actual message
    message = message[0].split(CHANNEL_DATA_SEPARATOR, 1)[1]

    message = json_decode(message)

    app_id = message.get("app_id")
    method = message.get("method")
    params = message.get("params")

    if app_id and app_id == application.uid:
        # application id must be set when we don't want to do
        # make things twice for the same application. Setting
        # app_id means that we don't want to process control
        # message when it is appear in application instance if
        # application uid matches app_id
        raise Return((True, None))

    if method == "unsubscribe":
        yield handle_unsubscribe(application, params)
    elif method == "update_state":
        yield handle_update_state()

    raise Return((True, None))


@coroutine
def handle_unsubscribe(app, params):
    """
    Unsubscribe client from certain channels provided in `block` call.
    """
    project = params.get("project")
    user = params.get("user")
    unsubscribe_from = params.get("from")

    if not user:
        # we don't need to block anonymous users
        raise Return((True, None))

    project_id = project['_id']

    # try to find user's connection
    user_connections = app.connections.get(project_id, {}).get(user, None)
    if not user_connections:
        raise Return((True, None))

    categories, error = yield state.get_project_categories(project)
    if error:
        raise Return((None, error))

    categories = dict(
        (x['name'], x) for x in categories
    )

    for uid, connection in six.iteritems(user_connections):

        if not unsubscribe_from:
            # unsubscribe from all channels
            for category_name, channels in six.iteritems(connection.channels):
                for channel_to_unsubscribe in channels:
                    connection.sub_stream.setsockopt_string(
                        zmq.UNSUBSCRIBE,
                        six.u(channel_to_unsubscribe)
                    )
            raise Return((True, None))

        for category_name, channels in six.iteritems(unsubscribe_from):

            category = categories.get(category_name, None)
            if not category:
                # category does not exist
                continue

            category_id = category['_id']

            if not channels:
                # here we should unsubscribe client from all channels
                # which belongs to category
                category_channels = connection.channels.get(category_name, None)
                if not category_channels:
                    continue
                for channel_to_unsubscribe in category_channels:
                    connection.sub_stream.setsockopt_string(
                        zmq.UNSUBSCRIBE,
                        six.u(channel_to_unsubscribe)
                    )
                try:
                    del connection.channels[category_name]
                except KeyError:
                    pass
            else:
                for channel in channels:
                    # unsubscribe from certain channel

                    channel_to_unsubscribe = create_channel_name(
                        project_id, category_id, channel
                    )

                    connection.sub_stream.setsockopt_string(
                        zmq.UNSUBSCRIBE,
                        six.u(channel_to_unsubscribe)
                    )

                    try:
                        del connection.channels[category_name][channel_to_unsubscribe]
                    except KeyError:
                        pass

    raise Return((True, None))


@coroutine
def handle_update_state():
    result, error = yield state.update()
    raise Return((result, error))


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