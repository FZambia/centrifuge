# coding: utf-8
import six
import uuid
from bson import ObjectId

import zmq
from zmq.eventloop.zmqstream import ZMQStream

import tornado.web
import tornado.ioloop
from tornado.gen import coroutine, Return
from tornado.escape import json_decode, json_encode


from . import utils


# separate important parts of channel name by this
CHANNEL_NAME_SEPARATOR = ':'


# add sequence of symbols to the end of each channel name to
# prevent name overlapping
CHANNEL_SUFFIX = '>>>'


def publish(stream, channel, message):
    """
    Publish message into channel of stream.
    """
    to_publish = [channel, message]
    stream.send_multipart(to_publish)


def create_channel_name(project_id, category_id, channel):
    return str(CHANNEL_NAME_SEPARATOR.join([
        'event',
        project_id,
        category_id,
        channel,
        CHANNEL_SUFFIX
    ]))


def parse_channel_name(channel):
    project_id, category_id, channel = channel.split(
        CHANNEL_NAME_SEPARATOR, 4
    )[1:4]
    return project_id, category_id, channel


def create_project_channel_name(project_id):
    return str(CHANNEL_NAME_SEPARATOR.join([
        'project',
        project_id,
        CHANNEL_SUFFIX
    ]))


def parse_project_channel_name(channel):
    project_id = channel.split(CHANNEL_NAME_SEPARATOR, 2)[1]
    return project_id


CONTROL_CHANNEL_NAME = '_control' + CHANNEL_SUFFIX


class Application(tornado.web.Application):

    def __init__(self, *args, **kwargs):

        self.zmq_context = zmq.Context()

        # create unique uid for this application
        self.uid = uuid.uuid4().hex

        # initialize dict to keep admin connections
        self.admin_connections = {}

        # initialize dict to keep client's connections
        self.connections = {}

        # dict to keep ping from nodes
        # key - node address, value - timestamp of last ping
        self.nodes = {}

        # application structure state (projects, categories etc)
        self.state = None

        # initialize dict to keep channel presence
        self.presence = {}

        # initialize dict to keep channel history
        self.history = {}

        # initialize dict to keep back-off information for projects
        self.back_off = {}

        # initialize tornado's application
        super(Application, self).__init__(*args, **kwargs)

    def init_sockets(self, options):
        """
        Routine to create all application-wide ZeroMQ sockets.
        """
        self.zmq_pub_sub_proxy = options.zmq_pub_sub_proxy

        # create PUB socket to publish instance events into it
        publish_socket = self.zmq_context.socket(zmq.PUB)
        # do not try to send messages after closing
        publish_socket.setsockopt(zmq.LINGER, 0)

        if self.zmq_pub_sub_proxy:
            # application started with XPUB/XSUB proxy
            self.zmq_xsub = options.zmq_xsub
            publish_socket.connect(self.zmq_xsub)
        else:
            # application started without XPUB/XSUB proxy
            if options.zmq_pub_port_shift:
                # calculate zmq pub port number
                zmq_pub_port = options.port + options.zmq_pub_port_shift
            else:
                zmq_pub_port = options.zmq_pub_port

            self.zmq_pub_port = zmq_pub_port

            publish_socket.bind(
                "tcp://%s:%s" % (options.zmq_pub_listen, str(self.zmq_pub_port))
            )

        # wrap pub socket into ZeroMQ stream
        self.pub_stream = ZMQStream(publish_socket)

        # create SUB socket listening to all events from all app instances
        subscribe_socket = self.zmq_context.socket(zmq.SUB)

        if self.zmq_pub_sub_proxy:
            # application started with XPUB/XSUB proxy
            self.zmq_xpub = options.zmq_xpub
            subscribe_socket.connect(self.zmq_xpub)
        else:
            # application started without XPUB/XSUB proxy
            self.zmq_sub_address = options.zmq_sub_address
            for address in self.zmq_sub_address:
                subscribe_socket.connect(address)

        subscribe_socket.setsockopt_string(
            zmq.SUBSCRIBE,
            six.u(CONTROL_CHANNEL_NAME)
        )

        def listen_control_channel():
            # wrap sub socket into ZeroMQ stream and set its on_recv callback
            self.sub_stream = ZMQStream(subscribe_socket)
            self.sub_stream.on_recv(self.handle_control_message)

        tornado.ioloop.IOLoop.instance().add_callback(
            listen_control_channel
        )

    @coroutine
    def handle_control_message(self, multipart_message):
        """
        Handle control message.
        """
        # extract actual message
        message = multipart_message[1]

        message = json_decode(message)

        app_id = message.get("app_id")
        method = message.get("method")
        params = message.get("params")

        if app_id and app_id == self.uid:
            # application id must be set when we don't want to do
            # make things twice for the same application. Setting
            # app_id means that we don't want to process control
            # message when it is appear in application instance if
            # application uid matches app_id
            raise Return((True, None))

        handle_func = None

        if method == "unsubscribe":
            handle_func = self.handle_unsubscribe
        elif method == "update_state":
            handle_func = self.handle_update_state

        if handle_func:
            result, error = yield handle_func(params)
            raise Return((result, error))
        else:
            raise Return((True, None))

    @coroutine
    def handle_unsubscribe(self, params):
        """
        Unsubscribe client from certain channels.
        """
        project = params.get("project")
        user = params.get("user")
        unsubscribe_from = params.get("from")

        if not user:
            # we don't need to block anonymous users
            raise Return((True, None))

        project_id = project['_id']

        # try to find user's connection
        user_connections = self.connections.get(project_id, {}).get(user, None)
        if not user_connections:
            raise Return((True, None))

        categories, error = yield self.state.get_project_categories(project)
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
    def handle_update_state(self, params):
        """
        Handle request to update state.
        """
        result, error = yield self.state.update()
        raise Return((result, error))

    @coroutine
    def handle_publish(self, params):
        """
        Handle publishing new message.
        """
        pass

    @coroutine
    def process_call(self, project, method, params):
        """
        Process HTTP call. It can be new message publishing or
        new command.
        """
        assert isinstance(project, dict)

        handle_func = None

        if method == "publish":
            handle_func = self.process_publish
            result, error = yield self.process_publish(
                project, params
            )
        elif method == "presence":
            handle_func = self.process_presence
        elif method == "history":
            handle_func = self.process_history
        else:
            params["project"] = project
            to_publish = {
                "method": method,
                "params": params
            }
            publish(
                self.pub_stream,
                CONTROL_CHANNEL_NAME,
                json_encode(to_publish)
            )
            result, error = True, None

        raise Return((result, error))

    @coroutine
    def publish_message(self, message, allowed_categories):
        """
        Publish event into PUB socket stream
        """
        project_id = message['project_id']
        category_id = message['category_id']
        category_name = message['category']

        message = json_encode(message)

        if allowed_categories[category_name]['publish_to_admins']:
            # send to project channel (only for admin use)
            channel = create_project_channel_name(project_id)
            publish(self.pub_stream, channel, message)

        # send to event channel
        channel = create_channel_name(
            project_id, category_id, message['channel']
        )
        publish(self.pub_stream, channel, message)

        raise Return((True, None))

    @coroutine
    def prepare_message(self, project, allowed_categories, params):
        """
        Prepare message before actual publishing.
        """
        opts = self.settings['options']

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

        message = {
            'project_id': project['_id'],
            'project': project['name'],
            'category_id': category['_id'],
            'category': category['name'],
            'event_id': str(ObjectId()),
            'channel': channel,
            'data': event_data
        }

        raise Return((message, None))

    @coroutine
    def process_publish(self, project, params, allowed_categories=None):

        if allowed_categories is None:
            project_categories, error = yield self.state.get_project_categories(project)
            if error:
                raise Return((None, error))

            allowed_categories = dict((x['name'], x) for x in project_categories)

        message, error = yield self.prepare_message(
            project, allowed_categories, params
        )
        if error:
            raise Return((None, error))

        if isinstance(message, dict):
            # event stored successfully and we can make callbacks
            result, error = yield self.publish_message(
                message, allowed_categories
            )
            if error:
                raise Return((None, error))
        else:
            # message is error description
            raise Return((None, message))

        raise Return((True, None))