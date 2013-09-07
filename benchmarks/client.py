import sys
import hmac
import six
import json
from twisted.internet import reactor
from autobahn.websocket import WebSocketClientFactory
from autobahn.websocket import WebSocketClientProtocol
from autobahn.websocket import connectWS


URL = sys.argv[1]
PROJECT_ID = sys.argv[2]
SECRET_KEY = sys.argv[3]
USER_ID = "test"

try:
    NUM_CLIENTS = int(sys.argv[4])
except IndexError:
    NUM_CLIENTS = 1


class ClientProtocol(WebSocketClientProtocol):
    """
    Simple client that connects to a WebSocket server, send a HELLO
    message every 2 seconds and print everything it receives.
    """

    user_id = "test"

    _connected = False

    _subscribed = False

    def centrifuge_connect(self):

        message = {
            "method": "connect",
            "params": {
                "token": generate_token(SECRET_KEY, PROJECT_ID, USER_ID),
                "user": USER_ID,
                "project": PROJECT_ID
            }
        }

        self.sendMessage(json.dumps(message))

    def centrifuge_subscribe(self):
        message = {
            "method": "subscribe",
            "params": {
                "namespace": "test",
                "channel": "test"
            }
        }

        self.sendMessage(json.dumps(message))

    def centrifuge_publish(self):
        message = {
            "method": "publish",
            "params": {
                "namespace": "test",
                "channel": "test",
                "data": "test"
            }
        }

        self.sendMessage(json.dumps(message))

    def on_centrifuge_message(self, msg):
        pass

    def onOpen(self):
        self.centrifuge_connect()

    def onMessage(self, msg, binary):
        msg = json.loads(msg)
        if msg['error']:
            print msg['error']
            raise

        method = msg['method']

        if method == 'connect':
            self._connected = True
            self.centrifuge_subscribe()
        elif method == 'subscribe':
            self._subscribed = True
            self.centrifuge_publish()
        else:
            self.on_centrifuge_message(msg)


def generate_token(secret_key, project_id, user_id):
    sign = hmac.new(six.b(str(secret_key)))
    sign.update(six.b(user_id))
    sign.update(six.b(str(project_id)))
    token = sign.hexdigest()
    return token


if __name__ == '__main__':

    if len(sys.argv) < 2:
        print "Need the WebSocket server address, i.e. ws://localhost:9000"
        sys.exit(1)

    factory = WebSocketClientFactory(URL)
    factory.protocol = ClientProtocol

    for i in range(NUM_CLIENTS):
        connectWS(factory)

    reactor.run()
