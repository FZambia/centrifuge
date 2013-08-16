/*
Centrifuge javascript browser client.

API reference:

To all commands we can bind success and error callbacks

connect(function() {connection now ready}).success().error();

centrifuge.on('connect', function() {
    the same as with anonymous above
});

centrifuge.on('connect:success', function() {
    instead of .success()
});

centrifuge.on('connect:error', function(){
    instead of .error()
});

disconnect(function() {now disconnected}).success()

- 'disconnect'
- 'disconnect:success'
- 'disconnect:error'

subscription = subscribe(path, function(message) {new message from this channel}).success().error()

subscription events:

- 'message'
- 'subscribe:success'
- 'subscribe:error'

subscription actions:

unsubscribe().success().error();

- 'unsubscribe:success'
- 'unsubscribe:error'

publish(content).success().error();

- 'publish:success'
- 'publish:error'

presence(function(data) {new presence message for this path}).success().error();

- 'presence'
- 'presence: success'
- 'presence: error'

history(function(data) {new history message for this path}).success().error();

- 'history'
- 'history: success'
- 'history: error'

 */

/**
 * Mixes in the given objects into the target object by copying the properties.
 * @param deep if the copy must be deep
 * @param target the target object
 * @param objects the objects whose properties are copied into the target
 */
function mixin(deep, target, objects) {
    var result = target || {};

    // Skip first 2 parameters (deep and target), and loop over the others
    for (var i = 2; i < arguments.length; ++i) {
        var object = arguments[i];

        if (object === undefined || object === null) {
            continue;
        }

        for (var propName in object) {
            //noinspection JSUnfilteredForInLoop
            var prop = fieldValue(object, propName);
            //noinspection JSUnfilteredForInLoop
            var targ = fieldValue(result, propName);

            // Avoid infinite loops
            if (prop === target) {
                continue;
            }
            // Do not mixin undefined values
            if (prop === undefined) {
                continue;
            }

            if (deep && typeof prop === 'object' && prop !== null) {
                if (prop instanceof Array) {
                    //noinspection JSUnfilteredForInLoop
                    result[propName] = this._mixin(deep, targ instanceof Array ? targ : [], prop);
                } else {
                    var source = typeof targ === 'object' && !(targ instanceof Array) ? targ : {};
                    //noinspection JSUnfilteredForInLoop
                    result[propName] = this._mixin(deep, source, prop);
                }
            } else {
                //noinspection JSUnfilteredForInLoop
                result[propName] = prop;
            }
        }
    }

    return result;
}

function fieldValue(object, name) {
    try {
        return object[name];
    } catch (x) {
        return undefined;
    }
}

function endsWith(value, suffix) {
    return value.indexOf(suffix, value.length - suffix.length) !== -1;
}

function stripSlash(value) {
    if (value.substring(value.length - 1) == "/") {
        value = value.substring(0, value.length - 1);
    }
    return value;
}

function isString(value) {
    if (value === undefined || value === null)
    {
        return false;
    }
    return typeof value === 'string' || value instanceof String;
}

function isFunction(value) {
    if (value === undefined || value === null)
    {
        return false;
    }
    return typeof value === 'function';
}

function log(level, args) {
    if (window.console) {
        var logger = window.console[level];
        if (isFunction(logger)) {
            logger.apply(window.console, args);
        }
    }
}


function Centrifuge(name) {
    this._name = name || 'default';
    this._sockjs = false;
    this._status = 'disconnected';
    this._transport = null;
    this._messageId = 0;
    this._clientId = null;
    this._listeners = {};
    this._callbacks = {};
    this._subscriptions = {};
    this._regex = /^\/([^_]+[A-z0-9]{2,})\/(.+)$/;
    this._config = {
        retry: 3000,
        logLevel: 'info'
    };
}

Centrifuge.inherit(EventEmitter);

cent_proto = Centrifuge.prototype;

cent_proto._debug = function() {
    if (this._config.logLevel === 'debug') {
        log('debug', arguments);
    }
};

cent_proto._configure = function(configuration) {
    this._debug('Configuring centrifuge object with', configuration);

    if (!configuration) {
        configuration = {};
    }

    this._config = mixin(false, this._config, configuration);

    if (!this._config.url) {
        throw 'Missing required configuration parameter \'url\' specifying the Centrifuge server URL';
    }

    if (!this._config.token) {
        throw 'Missing required configuration parameter \'token\' specifying the sign of authorization request';
    }

    if (!this._config.project) {
        throw 'Missing required configuration parameter \'project\' specifying project ID in Centrifuge';
    }

    if (!this._config.user) {
        throw 'Missing required configuration parameter \'user\' specifying user\'s unique ID in your application';
    }

    if (!this._config.permissions) {
        throw 'Missing required configuration parameter \'permissions\' specifying user\'s subscribe permissions';
    }

    this._config.url = stripSlash(this._config.url);

    if (endsWith(this._config.url, 'connection')) {
        //noinspection JSUnresolvedVariable
        if (typeof window.SockJS === 'undefined') {
            throw 'You need to include SockJS client library before Centrifuge javascript client library or use pure Websocket endpoint';
        }
        this._sockjs = true;
    }
};

cent_proto._parsePath = function(path) {
    var matches = this._regex.exec(path);
    if (!matches) {
        throw "Invalid channel to subscribe. Must be in format /category/channel"
    }
    var category = matches[1];
    var channel = matches[2];
    return [category, channel]
};

cent_proto._makePath = function(category, channel) {
    return '/' + category + '/' + channel;
};

cent_proto._setStatus = function(newStatus) {
    if (this._status !== newStatus) {
        this._debug('Status', this._status, '->', newStatus);
        this._status = newStatus;
    }
};

cent_proto._isDisconnected = function() {
    return this._isConnected() === false;
};

cent_proto._isConnected = function() {
    return this._status === 'connected';
};

cent_proto._nextMessageId = function() {
    return ++this._messageId;
};

cent_proto._clearSubscriptions = function() {
    this._subscriptions = {};
};

cent_proto._send = function(messages) {
    // We must be sure that the messages have a clientId.
    // This is not guaranteed since the handshake may take time to return
    // (and hence the clientId is not known yet) and the application
    // may create other messages.
    for (var i = 0; i < messages.length; ++i) {
        var message = messages[i];
        message.uid = '' + this._nextMessageId();

        if (this._clientId) {
            message.clientId = this._clientId;
        }

        var callback = undefined;

        if (isFunction(message._callback)) {
            callback = message._callback;
            delete message._callback;
        }

        if (callback)
            this._callbacks[message.uid] = callback;

        this._debug('Send', message);
        this._transport.send(JSON.stringify(message));
    }
};

cent_proto._connect = function() {

    this._clientId = null;

    console.log(this);

    this._clearSubscriptions();

    this._setStatus('connecting');

    if (this._sockjs === true) {
        //noinspection JSUnresolvedFunction
        this._transport = new SockJS(this._config.url);
    } else {
        this._transport = new WebSocket(this._config.url);
    }

    this._setStatus('connecting');

    var self = this;

    this._transport.onopen = function() {

        var centrifuge_message = {
            'method': 'connect',
            'params': {
                'token': self._config.token,
                'user': self._config.user,
                'project': self._config.project,
                'permissions': self._config.permissions
            }
        };
        var message = mixin(false, {}, centrifuge_message);
        self._send([message]);
    };

    this._transport.onclose = function() {
        self._setStatus('disconnected');
        self.trigger('disconnect');
        window.setTimeout(function() {
            self._connect.call(self)
        }, self._config.retry);
    };

    this._transport.onmessage = function(event) {
        var data;
        if (self._sockjs === true) {
            data = event.data;
        } else {
            data = JSON.parse(event.data);
        }
        self._receive(data);
    };
};

cent_proto._hasSubscription = function(path) {
    return path in this._subscriptions;
};

cent_proto._createSubscription = function(path) {
    var subscription = new Subscription(this, path);
    this._subscriptions[path] = subscription;
    return subscription;
};

cent_proto._removeSubscription = function(path) {
    try {
        delete this._subscriptions[path];
    } catch (e) {
        this._debug('nothing to delete for path ', path);
    }
};

cent_proto._connectResponse = function(message) {
    if (message.error === null) {
        this._clientId = message.body;
        this._setStatus('connected');
        this.trigger('connect', [message]);
    } else {
        this.trigger('error', [message]);
        this.trigger('connect:error', [message]);
    }
};

cent_proto._disconnectResponse = function(message) {
    if (message.error === null) {
        this._clientId = null;
        this._setStatus('disconnected');
        this.trigger('disconnect', [message]);
        this.trigger('disconnect:success', [message]);
    } else {
        this.trigger('error', [message]);
        this.trigger('disconnect:error', [message]);
    }
};

cent_proto._subscribeResponse = function(message) {
    var category = message.params["category"];
    var channel = message.params["channel"];
    var path = this._makePath(category, channel);
    var subscription = this._subscriptions[path];
    if (!subscription) {
        return
    }
    if (message.error === null) {
        subscription.trigger('subscribe:success', [message]);
    } else {
        subscription.trigger('subscribe:error', [message]);
        this.trigger('error', [message]);
    }
};

cent_proto._unsubscribeResponse = function(message) {
    var category = message.params["category"];
    var channel = message.params["channel"];
    var path = this._makePath(category, channel);
    var subscription = this._subscriptions[path];
    if (!subscription) {
        return
    }
    if (message.error === null) {
        subscription.trigger('unsubscribe:success', [message]);
    } else {
        subscription.trigger('unsubscribe:error', [message]);
        this.trigger('error', [message]);
    }
};

cent_proto._publishResponse = function(message) {
    var category = message.params["category"];
    var channel = message.params["channel"];
    var path = this._makePath(category, channel);
    var subscription = this._subscriptions[path];
    if (!subscription) {
        return
    }
    if (message.error === null) {
        subscription.trigger('publish:success', [message]);
    } else {
        subscription.trigger('publish:error', [message]);
        this.trigger('error', [message]);
    }
};

cent_proto._presenceResponse = function(message) {
    var category = message.params["category"];
    var channel = message.params["channel"];
    var path = this._makePath(category, channel);
    var subscription = this._subscriptions[path];
    if (!subscription) {
        return
    }
    if (message.error === null) {
        subscription.trigger('presence', [message.body]);
        subscription.trigger('presence:success', [message]);
    } else {
        subscription.trigger('presence:error', [message]);
        this.trigger('error', [message]);
    }
};

cent_proto._historyResponse = function(message) {
    var category = message.params["category"];
    var channel = message.params["channel"];
    var path = this._makePath(category, channel);
    var subscription = this._subscriptions[path];
    if (!subscription) {
        return
    }
    if (message.error === null) {
        subscription.trigger('history', [message.body]);
        subscription.trigger('history:success', [message]);
    } else {
        subscription.trigger('history:error', [message]);
        this.trigger('error', [message]);
    }
};

cent_proto._messageResponse = function(message) {
    if (message.body) {
        //noinspection JSValidateTypes
        var body = JSON.parse(message.body);
        var path = this._makePath(body.category, body.channel);
        var subscription = this._subscriptions[path];
        if (!subscription) {
            return
        }
        subscription.trigger('message', [body.data]);
    } else {
        this._debug('Unknown message', message);
    }
};

cent_proto._receive = function(message) {

    if (message === undefined || message === null) {
        return;
    }

    var method = message.method;

    switch (method) {
        case 'connect':
            this._connectResponse(message);
            break;
        case 'disconnect':
            this._disconnectResponse(message);
            break;
        case 'subscribe':
            this._subscribeResponse(message);
            break;
        case 'unsubscribe':
            this._unsubscribeResponse(message);
            break;
        case 'publish':
            this._publishResponse(message);
            break;
        case 'presence':
            this._presenceResponse(message);
            break;
        case 'history':
            this._historyResponse(message);
            break;
        case 'message':
            this._messageResponse(message);
            break;
        default:
            break;
    }
};

/* PUBLIC API */

cent_proto.parsePath = cent_proto._parsePath;

cent_proto.isConnected = cent_proto._isConnected;

cent_proto.isDisconnected = cent_proto._isDisconnected;

cent_proto.configure = function(configuration) {
    this._configure.call(this, configuration);
};

cent_proto.connect = cent_proto._connect;

cent_proto.removeSubscription = cent_proto._removeSubscription;

cent_proto.send = function(message) {
    this._send([message]);
};

cent_proto.subscribe = function(path, callback) {

    if (arguments.length < 1) {
        throw 'Illegal arguments number: required 1, got ' + arguments.length;
    }
    if (!isString(path)) {
        throw 'Illegal argument type: channel must be a string';
    }
    if (this.isDisconnected()) {
        throw 'Illegal state: already disconnected';
    }

    // Only send the message to the server if this client has not yet subscribed to the channel
    var send = !this._hasSubscription(path);

    var subscription = this._createSubscription(path);

    if (send) {
        subscription.subscribe(callback);
    }

    return subscription;
};

cent_proto.publish = function(path, data) {
    var subscription = this._subscriptions[path];
    console.log(this._subscriptions);
    if (!subscription) {
        this.trigger('error', ['no subscription to publish into for path ' + path]);
        return null;
    }
    subscription.publish(data);
    return subscription;
};

cent_proto.presence = function(path, callback) {
    var subscription = this._subscriptions[path];
    if (!subscription) {
        this.trigger('error', ['no subscription to get presence for path ' + path]);
        return null;
    }
    subscription.presence(callback);
    return subscription;
};

cent_proto.history = function(path, callback) {
    var subscription = this._subscriptions[path];
    if (!subscription) {
        this.trigger('error', ['no subscription to get history for path ' + path]);
        return null;
    }
    subscription.history(callback);
    return subscription;
};

function Subscription(centrifuge, path) {
    /**
     * The constructor for a centrifuge object, identified by an optional name.
     * The default name is the string 'default'.
     * @param name the optional name of this centrifuge object
     */
    this._centrifuge = centrifuge;
    this._path = path;
    var matches = this.parsePath();
    this.category = matches[0];
    this.channel = matches[1];
}

Subscription.inherit(EventEmitter);

sub_proto = Subscription.prototype;

sub_proto.getPath = function() {
    return this._path;
};

sub_proto.getCentrifuge = function() {
    return this._centrifuge;
};

sub_proto.parsePath = function() {
    return this._centrifuge.parsePath(this._path);
};

sub_proto.subscribe = function(callback) {
    var centrifugeMessage = {
        "method": "subscribe",
        "params": {
            "category": this.category,
            "channel": this.channel
        }
    };
    var message = mixin(false, {}, centrifugeMessage);
    this._centrifuge.send(message);
    this.on('message', callback);
};

sub_proto.unsubscribe = function() {
    this._centrifuge.removeSubscription(this.path);
    var centrifugeMessage = {
        "method": "unsubscribe",
        "params": {
            "category": this.category,
            "channel": this.channel
        }
    };
    var message = mixin(false, {}, centrifugeMessage);
    this._centrifuge.send(message);
};

sub_proto.publish = function(data) {
    var centrifugeMessage = {
        "method": "publish",
        "params": {
            "category": this.category,
            "channel": this.channel,
            "data": data
        }
    };
    var message = mixin(false, {}, centrifugeMessage);
    this._centrifuge.send(message);
};

sub_proto.presence = function(callback) {
    var centrifugeMessage = {
        "method": "presence",
        "params": {
            "category": this.category,
            "channel": this.channel
        }
    };
    if (callback) {
        this.on('presence', callback);
    }
    var message = mixin(false, {}, centrifugeMessage);
    this._centrifuge.send(message);
};

sub_proto.history = function(callback) {
    var centrifugeMessage = {
        "method": "history",
        "params": {
            "category": this.category,
            "channel": this.channel
        }
    };
    if (callback) {
        this.on('history', callback);
    }
    var message = mixin(false, {}, centrifugeMessage);
    this._centrifuge.send(message);
};
