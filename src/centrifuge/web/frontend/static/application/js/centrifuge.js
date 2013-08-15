
/*
This is a modified version of Cometd (http://cometdproject.dojotoolkit.org/) javascript client
adapted for Centrifuge.

Original CometD implementation can be found here:
https://github.com/cometd/cometd/blob/master/cometd-javascript/common/src/main/js/org/cometd/CometD.js

IMPLEMENTATION NOTES:
Be very careful in not changing the function order and pass this file every time through JSLint (http://jslint.com)
The only implied globals must be "dojo", "org" and "window", and check that there are no "unused" warnings
Failing to pass JSLint may result in shrinkers/minifiers to create an unusable file.


Centrifuge API reference:

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


Centrifuge = function(name) {
    /**
     * The constructor for a centrifuge object, identified by an optional name.
     * The default name is the string 'default'.
     * @param name the optional name of this centrifuge object
     */
    var _centrifuge = this;
    var _name = name || 'default';
    var _sockjs = false;
    var _status = 'disconnected';
    var _transport = null;
    var _messageId = 0;
    var _clientId = null;
    var _listeners = {};
    var _backoff = 0;
    var _callbacks = {};
    var _reestablish = false;
    var _connected = false;
    var _regex = /^\/([^_]+[A-z0-9]{2,})\/(.+)$/;
    var _config = {
        retry: 3000,
        logLevel: 'info'
    };

    function _fieldValue(object, name) {
        try {
            return object[name];
        } catch (x) {
            return undefined;
        }
    }

    /**
     * Mixes in the given objects into the target object by copying the properties.
     * @param deep if the copy must be deep
     * @param target the target object
     * @param objects the objects whose properties are copied into the target
     */
    this._mixin = function(deep, target, objects) {
        var result = target || {};

        // Skip first 2 parameters (deep and target), and loop over the others
        for (var i = 2; i < arguments.length; ++i) {
            var object = arguments[i];

            if (object === undefined || object === null) {
                continue;
            }

            for (var propName in object) {
                //noinspection JSUnfilteredForInLoop
                var prop = _fieldValue(object, propName);
                //noinspection JSUnfilteredForInLoop
                var targ = _fieldValue(result, propName);

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
    };

    function _endsWith(value, suffix) {
        return value.indexOf(suffix, value.length - suffix.length) !== -1;
    }

    function _stripSlash(value) {
        if (value.substring(value.length - 1) == "/") {
            value = value.substring(0, value.length - 1);
        }
        return value;
    }

    function _isString(value) {
        if (value === undefined || value === null)
        {
            return false;
        }
        return typeof value === 'string' || value instanceof String;
    }

    function _isFunction(value) {
        if (value === undefined || value === null)
        {
            return false;
        }
        return typeof value === 'function';
    }

    function _log(level, args) {
        if (window.console)
        {
            var logger = window.console[level];
            if (_isFunction(logger))
            {
                logger.apply(window.console, args);
            }
        }
    }

    this._debug = function() {
        if (_config.logLevel === 'debug')
        {
            _log('debug', arguments);
        }
    };

    function _parsePath(path) {
        var matches = _regex.exec(path);
        if (!matches) {
            throw "Invalid channel to subscribe. Must be in format /category/channel"
        }
        var category = matches[1];
        var channel = matches[2];
        return [category, channel]
    }

    function _configure(configuration) {
        _centrifuge._debug('Configuring centrifuge object with', configuration);

        if (!configuration) {
            configuration = {};
        }

        _config = _centrifuge._mixin(false, _config, configuration);

        if (!_config.url) {
            throw 'Missing required configuration parameter \'url\' specifying the Centrifuge server URL';
        }

        if (!_config.token) {
            throw 'Missing required configuration parameter \'token\' specifying the sign of authorization request';
        }

        if (!_config.project) {
            throw 'Missing required configuration parameter \'project\' specifying project ID in Centrifuge';
        }

        if (!_config.user) {
            throw 'Missing required configuration parameter \'user\' specifying user\'s unique ID in your application';
        }

        if (!_config.permissions) {
            throw 'Missing required configuration parameter \'permissions\' specifying user\'s subscribe permissions';
        }

        _config.url = _stripSlash(_config.url);

        if (_endsWith(_config.url, 'connection')) {
            //noinspection JSUnresolvedVariable
            if (typeof window.SockJS === 'undefined') {
                throw 'You need to include SockJS client library before Centrifuge javascript client library or use pure Websocket endpoint';
            }
            _sockjs = true;
        }

    }

    function _removeListener(subscription) {
        if (subscription) {
            var subscriptions = _listeners[subscription.channel];
            if (subscriptions && subscriptions[subscription.id]) {
                delete subscriptions[subscription.id];
                _centrifuge._debug('Removed', subscription.listener ? 'listener' : 'subscription', subscription);
            }
        }
    }

    function _removeSubscription(subscription) {
        if (subscription && !subscription.listener) {
            _removeListener(subscription);
        }
    }

    function _clearSubscriptions() {
        for (var channel in _listeners) {
            //noinspection JSUnfilteredForInLoop
            var subscriptions = _listeners[channel];
            if (subscriptions) {
                for (var i = 0; i < subscriptions.length; ++i) {
                    _removeSubscription(subscriptions[i]);
                }
            }
        }
    }

    function _setStatus(newStatus) {
        if (_status !== newStatus) {
            _centrifuge._debug('Status', _status, '->', newStatus);
            _status = newStatus;
        }
    }

    function _isDisconnected() {
        return _status === 'disconnecting' || _status === 'disconnected';
    }

    function _isConnected() {
        return _status === 'connected';
    }


    function _nextMessageId() {
        return ++_messageId;
    }

    function _notify(channel, message) {
        var subscriptions = _listeners[channel];
        if (subscriptions && subscriptions.length > 0)
        {
            for (var i = 0; i < subscriptions.length; ++i)
            {
                var subscription = subscriptions[i];
                // Subscriptions may come and go, so the array may have 'holes'
                if (subscription)
                {
                    try
                    {
                        subscription.on_message.call(subscription.scope, message);
                    }
                    catch (x)
                    {
                        _centrifuge._debug('Exception during notification', subscription, message, x);
                    }
                }
            }
        }
    }

    function _notifyListeners(channel, message) {
        // Notify direct listeners
        _notify(channel, message);

        /*
        // Notify the globbing listeners
        var channelParts = channel.split('/');
        var last = channelParts.length - 1;
        for (var i = last; i > 0; --i)
        {
            var channelPart = channelParts.slice(0, i).join('/') + '/*';
            // We don't want to notify /foo/* if the channel is /foo/bar/baz,
            // so we stop at the first non recursive globbing
            if (i === last)
            {
                _notify(channelPart, message);
            }
            // Add the recursive globber and notify
            channelPart += '*';
            _notify(channelPart, message);
        }
        */
    }

    /**
     * Delivers the messages to the centrifuge server
     * @param messages the array of messages to send
     */
    function _send(messages)
    {
        // We must be sure that the messages have a clientId.
        // This is not guaranteed since the handshake may take time to return
        // (and hence the clientId is not known yet) and the application
        // may create other messages.
        for (var i = 0; i < messages.length; ++i)
        {
            var message = messages[i];
            message.uid = '' + _nextMessageId();

            if (_clientId)
            {
                message.clientId = _clientId;
            }

            var callback = undefined;

            if (_isFunction(message._callback)) {
                callback = message._callback;
                delete message._callback;
            }

            if (message !== undefined && message !== null) {
                messages[i] = message;
                if (callback)
                    _callbacks[message.uid] = callback;
            } else {
                messages.splice(i--, 1);
            }
            _centrifuge._debug('Send', message);
            _transport.send(JSON.stringify(message));
        }
    }

    function _queueSend(message) {
        _send([message]);
    }

    /**
     * Sends a complete centrifuge message.
     * This method is exposed as a public so that extensions may use it
     * to send centrifuge message directly, for example in case of re-sending
     * messages that have already been sent but that for some reason must
     * be resent.
     */
    this.send = _queueSend;

    function _disconnect(abort) {
        if (abort) {
            _transport.abort();
        }
        _clientId = null;
        _setStatus('disconnected');
    }

    /**
     * Sends the initial handshake message
     */
    function _connect()
    {
        _clientId = null;

        _clearSubscriptions();

        _setStatus('connecting');

        if (_sockjs === true) {
            //noinspection JSUnresolvedFunction
            _transport = new SockJS(_config.url);
        } else {
            _transport = new WebSocket(_config.url);
        }

        _setStatus('connecting');

        _transport.onopen = function() {

            var centrifuge_message = {
                'method': 'connect',
                'params': {
                    'token': _config.token,
                    'user': _config.user,
                    'project': _config.project,
                    'permissions': _config.permissions
                }
            };

            _setStatus('authorizing');
            var message = _centrifuge._mixin(false, {}, centrifuge_message);
            _send([message]);
        };

        _transport.onclose = function() {
            _connected = false;
            _setStatus('disconnected');
            window.setTimeout(_connect, _config.retry);
        };

        _transport.onmessage = function(event) {
            var data;
            if (_sockjs === true) {
                data = event.data;
            } else {
                data = JSON.parse(event.data);
            }
            _receive(data);
        };

    }

    function _connectResponse(message) {
        _connected = message.error === null;

        if (_connected) {
            _clientId = message.body;
            _setStatus('connected');
            _notifyListeners('/_meta/connect', message);
        }
        else {
            _failConnect(message);
        }
    }

    function _failConnect(message) {
        // Notify the listeners after the status change but before the next action
        _notifyListeners('/_meta/connect', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }

    function _disconnectResponse(message) {
        if (message.error === null)
        {
            _disconnect(false);
            _notifyListeners('/_meta/disconnect', message);
        }
        else
        {
            _failDisconnect(message);
        }
    }

    function _failDisconnect(message) {
        _disconnect(true);
        _notifyListeners('/_meta/disconnect', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }

    function _subscribeResponse(message) {
        if (message.error === null) {
            _notifyListeners('/_meta/subscribe', message);
        } else {
            _failSubscribe(message);
        }
    }

    function _failSubscribe(message) {
        _notifyListeners('/_meta/subscribe', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }

    function _unsubscribeResponse(message) {
        if (message.error === null) {
            _notifyListeners('/_meta/unsubscribe', message);
        } else {
            _failUnsubscribe(message);
        }
    }

    function _failUnsubscribe(message) {
        _notifyListeners('/_meta/unsubscribe', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }

    function _publishResponse(message) {
        if (message.error === null) {
            _handleCallback(message);
            _notifyListeners('/_meta/publish', message);
        } else {
            _failPublish(message);
        }
    }

    function _failPublish(message) {
        _handleCallback(message);
        _notifyListeners('/_meta/publish', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }

    function _presenceResponse(message) {
        if (message.error === null) {
            _handleCallback(message);
            _notifyListeners('/_meta/presence', message);
        } else {
            _failPresence(message);
        }
    }

    function _failPresence(message) {
        _handleCallback(message);
        _notifyListeners('/_meta/presence', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }

    function _historyResponse(message) {
        if (message.error === null) {
            _handleCallback(message);
            _notifyListeners('/_meta/history', message);
        } else {
            _failHistory(message);
        }
    }

    function _failHistory(message) {
        _handleCallback(message);
        _notifyListeners('/_meta/history', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }

    function _handleCallback(message) {
        var callback = _callbacks[message.uid];
        if (_isFunction(callback))
        {
            delete _callbacks[message.uid];
            callback.call(_centrifuge, message);
        }
    }

    function _messageResponse(message) {
        if (message.method !== "message") {
            _centrifuge._debug('Unknown message', message);
            return;
        }

        if (message.body) {
            //noinspection JSValidateTypes
            var body = JSON.parse(message.body);
            var path = '/' + body.category + '/' + body.channel;
            console.log(body);
            // It is a plain message, and not a bayeux meta message
            _notifyListeners(path, body.data);
        } else {
            _centrifuge._debug('Unknown message', message);
        }
    }

    function _receive(message)
    {
        if (message === undefined || message === null)
        {
            return;
        }

        var method = message.method;

        console.log(message.error);

        switch (method) {
            case 'connect':
                _connectResponse(message);
                break;
            case 'disconnect':
                _disconnectResponse(message);
                break;
            case 'subscribe':
                _subscribeResponse(message);
                break;
            case 'unsubscribe':
                _unsubscribeResponse(message);
                break;
            case 'publish':
                _publishResponse(message);
                break;
            case 'presence':
                _presenceResponse(message);
                break;
            case 'history':
                _historyResponse(message);
                break;
            default:
                _messageResponse(message);
                break;
        }
    }

    /**
     * Receives a message.
     * This method is exposed as a public so that extensions may inject
     * messages simulating that they had been received.
     */
    this.receive = _receive;

    function _hasSubscriptions(channel)
    {
        var subscriptions = _listeners[channel];
        if (subscriptions)
        {
            for (var i = 0; i < subscriptions.length; ++i)
            {
                if (subscriptions[i])
                {
                    return true;
                }
            }
        }
        return false;
    }

    function _addListener(channel, on_message_callback, isListener)
    {
        // The data structure is a map<channel, subscription[]>, where each subscription
        // holds the callback to be called and its scope.

        _centrifuge._debug('Adding', isListener ? 'listener' : 'subscription', 'on', channel);

        var subscription = {
            channel: channel,
            on_message: on_message_callback,
            listener: isListener,
            scope: _centrifuge,
            callback: function(calle) {
                console.log(calle);
                return subscription;
            },
            errback: function(calle) {
                console.log(calle);
                return subscription;
            }
        };

        var subscriptions = _listeners[channel];
        if (!subscriptions)
        {
            subscriptions = [];
            _listeners[channel] = subscriptions;
        }

        // Pushing onto an array appends at the end and returns the id associated with the element increased by 1.
        // Note that if:
        // a.push('a'); var hb=a.push('b'); delete a[hb-1]; var hc=a.push('c');
        // then:
        // hc==3, a.join()=='a',,'c', a.length==3
        subscription.id = subscriptions.push(subscription) - 1;

        _centrifuge._debug('Added', isListener ? 'listener' : 'subscription', subscription);

        return subscription;
    }

    //
    // PUBLIC API
    //

    /**
     * Configures the initial Centrifuge communication with the Centrifuge server.
     * Configuration is passed via an object that must contain a mandatory field <code>url</code>
     * of type string containing the URL of the Centrifuge server.
     * @param configuration the configuration object
     */
    this.configure = function(configuration) {
        _configure.call(this, configuration);
    };

    /**
     * Establishes the Centrifuge communication with the Centrifuge server
     * via a handshake and a subsequent connect.
     */
    this.connect = function() {
        _setStatus('disconnected');
        _reestablish = false;
        _connect();
    };

    /**
     * Disconnects from the Centrifuge server.
     */
    this.disconnect = function() {
        if (_isDisconnected()) {
            return;
        }

        var centrifuge_message = {
            method: 'disconnect'
        };
        var message = this._mixin(false, {}, centrifuge_message);
        _setStatus('disconnecting');
        _send([message]);
    };

    /**
     * Adds a listener for centrifuge messages, performing the given callback in the given scope
     * when a message for the given channel arrives.
     * @param channel the channel the listener is interested to
     * @param callback the callback to call when a message is sent to the channel
     * @returns the subscription handle to be passed to {@link #removeListener(object)}
     * @see #removeListener(subscription)
     */
    this.addListener = function(channel, callback)
    {
        if (arguments.length < 2)
        {
            throw 'Illegal arguments number: required 2, got ' + arguments.length;
        }
        if (!_isString(channel))
        {
            throw 'Illegal argument type: channel must be a string';
        }

        return _addListener(channel, callback, true);
    };

    /**
     * Removes the subscription obtained with a call to {@link #addListener(string, object, function)}.
     * @param subscription the subscription to unsubscribe.
     * @see #addListener(channel, scope, callback)
     */
    this.removeListener = function(subscription)
    {
        // Beware of subscription.id == 0, which is falsy => cannot use !subscription.id
        if (!subscription || !subscription.channel || !("id" in subscription))
        {
            throw 'Invalid argument: expected subscription, not ' + subscription;
        }

        _removeListener(subscription);
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Removes all listeners registered with {@link #addListener(channel, scope, callback)} or
     * {@link #subscribe(channel, scope, callback)}.
     */
    this.clearListeners = function()
    {
        _listeners = {};
    };

    /**
     * Subscribes to the given channel, performing the given callback in the given scope
     * when a message for the channel arrives.
     * @param path the channel to subscribe to
     * @param callback the callback to call when a message is sent to the channel
     * @return the subscription handle to be passed to {@link #unsubscribe(object)}
     */
    this.subscribe = function(path, callback) {

        if (arguments.length < 2)
        {
            throw 'Illegal arguments number: required 2, got ' + arguments.length;
        }
        if (!_isString(path))
        {
            throw 'Illegal argument type: channel must be a string';
        }
        if (_isDisconnected())
        {
            throw 'Illegal state: already disconnected';
        }

        // Only send the message to the server if this client has not yet subscribed to the channel
        var send = !_hasSubscriptions(path);

        var subscription = _addListener(path, callback, false);

        if (send)
        {
            var matches = _parsePath(path);
            var category = matches[0];
            var channel = matches[1];

            var centrifugeMessage = {
                "method": "subscribe",
                "params": {
                    "category": category,
                    "channel": channel
                }
            };
            var message = this._mixin(false, {}, centrifugeMessage);
            _send([message]);
        }

        return subscription;
    };

    /**
     * Unsubscribes the subscription obtained with a call to {@link #subscribe(string, object, function)}.
     * @param subscription the subscription to unsubscribe.
     */
    this.unsubscribe = function(subscription) {

        if (arguments.length < 1) {
            throw 'Illegal arguments number: required 1, got ' + arguments.length;
        }
        if (_isDisconnected()) {
            throw 'Illegal state: already disconnected';
        }

        // Remove the local listener before sending the message
        // This ensures that if the server fails, this client does not get notifications
        this.removeListener(subscription);

        var path = subscription.channel;
        // Only send the message to the server if this client unsubscribes the last subscription
        if (!_hasSubscriptions(path)) {
            var matches = _parsePath(path);
            var category = matches[0];
            var channel = matches[1];

            var centrifugeMessage = {
                "method": "unsubscribe",
                "params": {
                    "category": category,
                    "channel": channel
                }
            };
            var message = this._mixin(false, {}, centrifugeMessage);
            _send([message]);
        }
    };

    //noinspection JSUnusedGlobalSymbols
    this.resubscribe = function(subscription, subscribeProps)
    {
        _removeSubscription(subscription);
        if (subscription) {
            return this.subscribe(subscription.channel, subscription.scope, subscription.callback, subscribeProps);
        }
        return undefined;
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Removes all subscriptions added via {@link #subscribe(channel, scope, callback, subscribeProps)},
     * but does not remove the listeners added via {@link addListener(channel, scope, callback)}.
     */
    this.clearSubscriptions = function()
    {
        _clearSubscriptions();
    };

    /**
     * Publishes a message on the given channel, containing the given content.
     * @param path the channel to publish the message to
     * @param content the content of the message
     * @param publishCallback a function to be invoked when the publish is acknowledged by the server
     */
    this.publish = function(path, content, publishCallback) {
        if (arguments.length < 2)
        {
            throw 'Illegal arguments number: required 2, got ' + arguments.length;
        }
        if (!_isString(path))
        {
            throw 'Illegal argument type: channel must be a string';
        }
        if (_isDisconnected())
        {
            throw 'Illegal state: already disconnected';
        }

        var matches = _parsePath(path);
        var category = matches[0];
        var channel = matches[1];

        var centrifugeMessage = {
            "method": "publish",
            "params": {
                "category": category,
                "channel": channel,
                "data": content
            },
            _callback: publishCallback
        };
        var message = this._mixin(false, {}, centrifugeMessage);
        _send([message]);
    };

    this.presence = function(path, presenceCallback) {
        if (arguments.length < 2) {
            throw 'Illegal arguments number: required 2, got ' + arguments.length;
        }
        if (!_isString(path)) {
            throw 'Illegal argument type: channel must be a string';
        }
        if (_isDisconnected())
        {
            throw 'Illegal state: already disconnected';
        }

        var matches = _parsePath(path);
        var category = matches[0];
        var channel = matches[1];

        var centrifugeMessage = {
            "method": "presence",
            "params": {
                "category": category,
                "channel": channel
            },
            _callback: presenceCallback
        };
        var message = this._mixin(false, {}, centrifugeMessage);
        _send([message]);
    };

    this.history = function(path, historyCallback) {
        if (arguments.length < 2) {
            throw 'Illegal arguments number: required 2, got ' + arguments.length;
        }
        if (!_isString(path)) {
            throw 'Illegal argument type: channel must be a string';
        }
        if (_isDisconnected())
        {
            throw 'Illegal state: already disconnected';
        }

        var matches = _parsePath(path);
        var category = matches[0];
        var channel = matches[1];

        var centrifugeMessage = {
            "method": "history",
            "params": {
                "category": category,
                "channel": channel
            },
            _callback: historyCallback
        };
        var message = this._mixin(false, {}, centrifugeMessage);
        _send([message]);
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Returns a string representing the status of the centrifuge communication with the Centrifuge server.
     */
    this.getStatus = function() {
        return _status;
    };

    /**
     * Returns whether this instance has been disconnected.
     */
    this.isDisconnected = _isDisconnected;

    /**
     * Returns whether this instance connected.
     */
    this.isConnected = _isConnected;

    /**
     * Sets the backoff period used to increase the backoff time when retrying an unsuccessful or failed message.
     * Default value is 1 second, which means if there is a persistent failure the retries will happen
     * after 1 second, then after 2 seconds, then after 3 seconds, etc. So for example with 15 seconds of
     * elapsed time, there will be 5 retries (at 1, 3, 6, 10 and 15 seconds elapsed).
     * @param period the backoff period to set
     * @see #getBackoffIncrement()
     */
    this.setBackoffIncrement = function(period) {
        _config.backoffIncrement = period;
    };

    /**
     * Returns the backoff period used to increase the backoff time when retrying an unsuccessful or failed message.
     * @see #setBackoffIncrement(period)
     */
    this.getBackoffIncrement = function()
    {
        return _config.backoffIncrement;
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Returns the backoff period to wait before retrying an unsuccessful or failed message.
     */
    this.getBackoffPeriod = function()
    {
        return _backoff;
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Sets the log level for console logging.
     * Valid values are the strings 'error', 'warn', 'info' and 'debug', from
     * less verbose to more verbose.
     * @param level the log level string
     */
    this.setLogLevel = function(level)
    {
        _config.logLevel = level;
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Returns the name assigned to this centrifuge object, or the string 'default'
     * if no name has been explicitly passed as parameter to the constructor.
     */
    this.getName = function()
    {
        return _name;
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Returns the clientId assigned by the Centrifuge server during handshake.
     */
    this.getClientId = function()
    {
        return _clientId;
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Returns the URL of the Centrifuge server.
     */
    this.getURL = function()
    {
        return _config.url;
    };

    //noinspection JSUnusedGlobalSymbols
    this.getTransport = function()
    {
        return _transport;
    };

    //noinspection JSUnusedGlobalSymbols
    this.getConfiguration = function()
    {
        return this._mixin(true, {}, _config);
    };

    this.parsePath = _parsePath;
};



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


function Center(name) {
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

Center.inherit(EventEmitter);

cent_proto = Center.prototype;

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
    return this._status !== 'connected';
};

cent_proto._isConnected = function() {
    return this._isDisconnected() === false;
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
        window.setTimeout(self._connect, self._config.retry);
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
        subscription.subscribe(path, callback);
    }

    return subscription;
};

cent_proto._connectResponse = function(message) {
    if (message.error === null) {
        this._clientId = message.body;
        this._setStatus('connected');
        this.trigger('connect', message);
    } else {
        this.trigger('error', message);
        this.trigger('connect:error', message);
    }
};

cent_proto._disconnectResponse = function(message) {
    if (message.error === null) {
        this._clientId = null;
        this._setStatus('disconnected');
        this.trigger('disconnect', message);
        this.trigger('disconnect:success', message);
    } else {
        this.trigger('error', message);
        this.trigger('disconnect:error', message);
    }
};

cent_proto._subscribeResponse = function(message) {
    if (message.error === null) {
        for (var i = 0, len = message.body.length; i < len; i++) {
            var category = message.body[i][0];
            var channel = message.body[i][1];
            var path = this._makePath(category, channel);
            var subscription = this._subscriptions[path];
            if (subscription) {
                subscription.trigger('subscribe:success', message);
            }
        }
    } else {
        this.trigger('error', message);
    }
};

cent_proto._unsubscribeResponse = function(message) {
    if (message.error === null) {
        for (var i = 0, len = message.body.length; i < len; i++) {
            var category = message.body[i][0];
            var channel = message.body[i][1];
            var path = this._makePath(category, channel);
            var subscription = this._subscriptions[path];
            if (subscription) {
                subscription.trigger('unsubscribe:success', message);
            }
        }
    } else {
        this.trigger('error', message);
    }
};

cent_proto._publishResponse = function(message) {
    var category = message.body[0];
    var channel = message.body[1];
    var path = this._makePath(category, channel);
    var subscription = this._subscriptions[path];
    if (!subscription) {
        return
    }
    if (message.error === null) {
        if (subscription) {
            subscription.trigger('publish:success', message);
        }
    } else {
        this.trigger('error', message);
        if (subscription) {
            subscription.trigger('publish:error', message);
        }
    }
};

cent_proto._presenceResponse = function(message) {
    var category = message.body[0];
    var channel = message.body[1];
    var path = this._makePath(category, channel);
    var subscription = this._subscriptions[path];
    if (!subscription) {
        return
    }
    if (message.error === null) {
        if (subscription) {
            subscription.trigger('presence', message.body);
            subscription.trigger('presence:success', message);
        }
    } else {
        this.trigger('error', message);
        if (subscription) {
            subscription.trigger('presence:error', message);
        }
    }
};

cent_proto._historyResponse = function(message) {
    var category = message.body[0];
    var channel = message.body[1];
    var path = this._makePath(category, channel);
    var subscription = this._subscriptions[path];
    if (!subscription) {
        return
    }
    if (message.error === null) {
        if (subscription) {
            subscription.trigger('history', message.body);
            subscription.trigger('history:success', message);
        }
    } else {
        this.trigger('error', message);
        if (subscription) {
            subscription.trigger('history:error', message);
        }
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
        subscription.trigger('message', body.data);
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

cent_proto.configure = function(configuration) {
    this._configure.call(this, configuration);
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