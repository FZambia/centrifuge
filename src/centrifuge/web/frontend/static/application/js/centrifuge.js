/*
 *
 *  Centrifuge javascript browser client.
 *
 */
(function () {
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
                        result[propName] = mixin(deep, targ instanceof Array ? targ : [], prop);
                    } else {
                        var source = typeof targ === 'object' && !(targ instanceof Array) ? targ : {};
                        //noinspection JSUnfilteredForInLoop
                        result[propName] = mixin(deep, source, prop);
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

    function Centrifuge(options) {
        this._sockjs = false;
        this._status = 'disconnected';
        this._reconnect = true;
        this._transport = null;
        this._messageId = 0;
        this._clientId = null;
        this._subscriptions = {};
        this._fullRegex = /^\/([^_]+[A-z0-9]{2,})\/(.+)$/;
        this._channelOnlyRegex =/^\/(.+)$/;
        this._config = {
            retry: 3000,
            debug: false,
            protocols_whitelist: [
                'websocket',
                'xdr-streaming',
                'xhr-streaming',
                'iframe-eventsource',
                'iframe-htmlfile',
                'xdr-polling',
                'xhr-polling',
                'iframe-xhr-polling',
                'jsonp-polling'
            ]
        };
        if (options) {
            this.configure(options);
        }
    }

    Centrifuge.inherit(EventEmitter);

    var centrifuge_proto = Centrifuge.prototype;

    centrifuge_proto._debug = function() {
        if (this._config.debug === true) {
            log('debug', arguments);
        }
    };

    centrifuge_proto._configure = function(configuration) {
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

        this._config.url = stripSlash(this._config.url);

        if (endsWith(this._config.url, 'connection')) {
            //noinspection JSUnresolvedVariable
            if (typeof window.SockJS === 'undefined') {
                throw 'You need to include SockJS client library before Centrifuge javascript client library or use pure Websocket endpoint';
            }
            this._sockjs = true;
        }
    };

    centrifuge_proto._parsePath = function(path) {
        var channel, namespace;
        var fullMatches = this._fullRegex.exec(path);
        if (fullMatches) {
            namespace = fullMatches[1];
            channel = fullMatches[2];
        } else {
            var channelOnlyMatches = this._channelOnlyRegex.exec(path);
            if (!channelOnlyMatches) {
                throw 'Invalid path';
            }
            namespace = null;
            channel = channelOnlyMatches[1];
        }
        return [namespace, channel]
    };

    centrifuge_proto._makePath = function(namespace, channel) {
        if (namespace === null || namespace == undefined) {
            return '/' + channel;
        }
        return '/' + namespace + '/' + channel;
    };

    centrifuge_proto._setStatus = function(newStatus) {
        if (this._status !== newStatus) {
            this._debug('Status', this._status, '->', newStatus);
            this._status = newStatus;
        }
    };

    centrifuge_proto._isDisconnected = function() {
        return this._isConnected() === false;
    };

    centrifuge_proto._isConnected = function() {
        return this._status === 'connected';
    };

    centrifuge_proto._nextMessageId = function() {
        return ++this._messageId;
    };

    centrifuge_proto._clearSubscriptions = function() {
        this._subscriptions = {};
    };

    centrifuge_proto._send = function(messages) {
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

            this._debug('Send', message);
            this._transport.send(JSON.stringify(message));
        }
    };

    centrifuge_proto._connect = function(callback) {

        this._clientId = null;

        this._reconnect = true;

        this._clearSubscriptions();

        this._setStatus('connecting');

        var self = this;

        if (callback) {
            this.on('connect', callback);
        }

        if (this._sockjs === true) {
            //noinspection JSUnresolvedFunction
            this._transport = new SockJS(this._config.url, null, {
                protocols_whitelist: this._config.protocols_whitelist
            });

        } else {
            this._transport = new WebSocket(this._config.url);
        }

        this._setStatus('connecting');

        this._transport.onopen = function() {

            var centrifuge_message = {
                'method': 'connect',
                'params': {
                    'token': self._config.token,
                    'user': self._config.user,
                    'project': self._config.project
                }
            };
            var message = mixin(false, {}, centrifuge_message);
            self._send([message]);
        };

        this._transport.onerror = function(error) {
            this._debug(error);
        };

        this._transport.onclose = function() {
            self._setStatus('disconnected');
            self.trigger('disconnect');
            if (self._reconnect === true) {
                window.setTimeout(function() {
                    if (self._reconnect === true) {
                        self._connect.call(self)
                    }
                }, self._config.retry);
            }
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

    centrifuge_proto._disconnect = function() {
        this._clientId = null;
        this._setStatus('disconnected');
        this._subscriptions = {};
        this._reconnect = false;
        this._transport.close();
    };

    centrifuge_proto._hasSubscription = function(path) {
        return path in this._subscriptions;
    };

    centrifuge_proto._getSubscription = function(path) {
        var subscription = this._subscriptions[path];
        if (!subscription) {
            return null;
        }
        return subscription;
    };

    centrifuge_proto._createSubscription = function(path) {
        var subscription = new Subscription(this, path);
        this._subscriptions[path] = subscription;
        return subscription;
    };

    centrifuge_proto._removeSubscription = function(path) {
        try {
            delete this._subscriptions[path];
        } catch (e) {
            this._debug('nothing to delete for path ', path);
        }
    };

    centrifuge_proto._connectResponse = function(message) {
        if (message.error === null) {
            this._clientId = message.body;
            this._setStatus('connected');
            this.trigger('connect', [message]);
        } else {
            this.trigger('error', [message]);
            this.trigger('connect:error', [message]);
        }
    };

    centrifuge_proto._disconnectResponse = function(message) {
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

    centrifuge_proto._subscribeResponse = function(message) {
        var namespace = message.params["namespace"];
        var channel = message.params["channel"];
        var path = this._makePath(namespace, channel);
        var subscription = this._subscriptions[path];
        if (!subscription) {
            return;
        }
        if (message.error === null) {
            subscription.trigger('subscribe:success', [message]);
        } else {
            subscription.trigger('subscribe:error', [message]);
            this.trigger('error', [message]);
        }
    };

    centrifuge_proto._unsubscribeResponse = function(message) {
        var namespace = message.params["namespace"];
        var channel = message.params["channel"];
        var path = this._makePath(namespace, channel);
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

    centrifuge_proto._publishResponse = function(message) {
        var namespace = message.params["namespace"];
        var channel = message.params["channel"];
        var path = this._makePath(namespace, channel);
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

    centrifuge_proto._presenceResponse = function(message) {
        var namespace = message.params["namespace"];
        var channel = message.params["channel"];
        var path = this._makePath(namespace, channel);
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

    centrifuge_proto._historyResponse = function(message) {
        var namespace = message.params["namespace"];
        var channel = message.params["channel"];
        var path = this._makePath(namespace, channel);
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

    centrifuge_proto._messageResponse = function(message) {
        if (message.body) {
            //noinspection JSValidateTypes
            var subscription, path;
            var body = JSON.parse(message.body);
            path = this._makePath(body.namespace, body.channel);
            subscription = this._subscriptions[path];
            if (!subscription) {
                path = this._makePath(null, body.channel);
                subscription = this._subscriptions[path];
                if (!subscription) {
                    return;
                }
            }
            subscription.trigger('message', [body]);
        } else {
            this._debug('Unknown message', message);
        }
    };

    centrifuge_proto._receive = function(message) {

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

    centrifuge_proto.getClientId = function() {
        return this._clientId;
    };

    centrifuge_proto.parsePath = centrifuge_proto._parsePath;

    centrifuge_proto.isConnected = centrifuge_proto._isConnected;

    centrifuge_proto.isDisconnected = centrifuge_proto._isDisconnected;

    centrifuge_proto.configure = function(configuration) {
        this._configure.call(this, configuration);
    };

    centrifuge_proto.connect = centrifuge_proto._connect;

    centrifuge_proto.disconnect = centrifuge_proto._disconnect;

    centrifuge_proto.getSubscription = centrifuge_proto._getSubscription;

    centrifuge_proto.removeSubscription = centrifuge_proto._removeSubscription;

    centrifuge_proto.send = function(message) {
        this._send([message]);
    };

    centrifuge_proto.subscribe = function(path, callback) {

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

    centrifuge_proto.publish = function(path, data, callback) {
        var subscription = this._subscriptions[path];
        if (!subscription) {
            //this.trigger('error', ['no subscription to publish into for path ' + path]);
            return null;
        }
        subscription.publish(data, callback);
        return subscription;
    };

    centrifuge_proto.presence = function(path, callback) {
        var subscription = this._subscriptions[path];
        if (!subscription) {
            //this.trigger('error', ['no subscription to get presence for path ' + path]);
            return null;
        }
        subscription.presence(callback);
        return subscription;
    };

    centrifuge_proto.history = function(path, callback) {
        var subscription = this._subscriptions[path];
        if (!subscription) {
            //this.trigger('error', ['no subscription to get history for path ' + path]);
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
        this.namespace = matches[0];
        this.channel = matches[1];
    }

    Subscription.inherit(EventEmitter);

    var sub_proto = Subscription.prototype;

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
                "namespace": this.namespace,
                "channel": this.channel
            }
        };
        if (this.namespace === null) {
            // using default namespace
            delete centrifugeMessage["params"]["namespace"];
        }
        var message = mixin(false, {}, centrifugeMessage);
        this._centrifuge.send(message);
        if (callback) {
            this.on('message', callback);
        }
    };

    sub_proto.unsubscribe = function() {
        this._centrifuge.removeSubscription(this.path);
        var centrifugeMessage = {
            "method": "unsubscribe",
            "params": {
                "namespace": this.namespace,
                "channel": this.channel
            }
        };
        if (this.namespace === null) {
            // using default namespace
            delete centrifugeMessage["params"]["namespace"];
        }
        var message = mixin(false, {}, centrifugeMessage);
        this._centrifuge.send(message);
    };

    sub_proto.publish = function(data, callback) {
        var centrifugeMessage = {
            "method": "publish",
            "params": {
                "namespace": this.namespace,
                "channel": this.channel,
                "data": data
            }
        };
        if (this.namespace === null) {
            // using default namespace
            delete centrifugeMessage["params"]["namespace"];
        }
        if (callback) {
            this.on('publish:success', callback);
        }
        var message = mixin(false, {}, centrifugeMessage);
        this._centrifuge.send(message);
    };

    sub_proto.presence = function(callback) {
        var centrifugeMessage = {
            "method": "presence",
            "params": {
                "namespace": this.namespace,
                "channel": this.channel
            }
        };
        if (this.namespace === null) {
            // using default namespace
            delete centrifugeMessage["params"]["namespace"];
        }
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
                "namespace": this.namespace,
                "channel": this.channel
            }
        };
        if (this.namespace === null) {
            // using default namespace
            delete centrifugeMessage["params"]["namespace"];
        }
        if (callback) {
            this.on('history', callback);
        }
        var message = mixin(false, {}, centrifugeMessage);
        this._centrifuge.send(message);
    };

    window.Centrifuge = Centrifuge;
    window.CentrifugeSubscription = Subscription;

})();
