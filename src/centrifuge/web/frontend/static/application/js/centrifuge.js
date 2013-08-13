/*
This is a modified version of Cometd (http://cometdproject.dojotoolkit.org/) javascript client
adapted for Centrifuge.

Original CometD implementation can be found here:
https://github.com/cometd/cometd/blob/master/cometd-javascript/common/src/main/js/org/cometd/CometD.js

IMPLEMENTATION NOTES:
Be very careful in not changing the function order and pass this file every time through JSLint (http://jslint.com)
The only implied globals must be "dojo", "org" and "window", and check that there are no "unused" warnings
Failing to pass JSLint may result in shrinkers/minifiers to create an unusable file.
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
    var _publishCallbacks = {};
    var _presenceCallbacks = {};
    var _historyCallbacks = {};
    var _reestablish = false;
    var _connected = false;
    var _regex = /^\/([^_]+[A-z0-9]{2,})\/(.+)$/;
    var _config = {
        reconnectTimeout: 3000,
        protocol: null,
        connectTimeout: 0,
        maxConnections: 2,
        backoffIncrement: 1000,
        maxBackoff: 60000,
        logLevel: 'info',
        maxNetworkDelay: 10000,
        requestHeaders: {}
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
                        subscription.callback.call(subscription.scope, message);
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

            var publishCallback = undefined;
            var presenceCallback = undefined;
            var historyCallback = undefined;

            if (_isFunction(message._publishCallback)) {
                publishCallback = message._publishCallback;
                delete message._publishCallback;
            } else if (_isFunction(message._presenceCallback)) {
                presenceCallback = message._presenceCallback;
                delete message._presenceCallback;
            } else if (_isFunction(message._historyCallback)) {
                historyCallback = message._historyCallback;
                delete message._historyCallback;
            }

            if (message !== undefined && message !== null) {
                messages[i] = message;
                if (publishCallback)
                    _publishCallbacks[message.uid] = publishCallback;
                if (presenceCallback)
                    _presenceCallbacks[message.uid] = presenceCallback;
                if (historyCallback)
                    _historyCallbacks[message.uid] = historyCallback;
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

    function _resetBackoff() {
        _backoff = 0;
    }

    function _increaseBackoff() {
        if (_backoff < _config.maxBackoff) {
            _backoff += _config.backoffIncrement;
        }
    }

    function _disconnect(abort) {
        if (abort) {
            _transport.abort();
        }
        _clientId = null;
        _setStatus('disconnected');
        _resetBackoff();
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
            console.log('OPA2');
            window.setTimeout(_connect, _config.reconnectTimeout);
        };

        _transport.onmessage = function(event) {
            var data;
            if (_sockjs === true) {
                data = event.data;
            } else {
                data = $.parseJSON(event.data);
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
            _handleCallback(_publishCallbacks, message);
            _notifyListeners('/_meta/publish', message);
        } else {
            _failPublish(message);
        }
    }

    function _failPublish(message) {
        _handleCallback(_publishCallbacks, message);
        _notifyListeners('/_meta/publish', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }

    function _presenceResponse(message) {
        if (message.error === null) {
            _handleCallback(_presenceCallbacks, message);
            _notifyListeners('/_meta/presence', message);
        } else {
            _failPresence(message);
        }
    }

    function _failPresence(message) {
        _handleCallback(_presenceCallbacks, message);
        _notifyListeners('/_meta/presence', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }

    function _historyResponse(message) {
        if (message.error === null) {
            _handleCallback(_historyCallbacks, message);
            _notifyListeners('/_meta/history', message);
        } else {
            _failHistory(message);
        }
    }

    function _failHistory(message) {
        _handleCallback(_historyCallbacks, message);
        _notifyListeners('/_meta/history', message);
        _notifyListeners('/_meta/unsuccessful', message);
    }


    function _handleCallback(store, message)
    {
        var callback = store[message.uid];
        if (_isFunction(callback))
        {
            delete store[message.uid];
            callback.call(_centrifuge, message);
        }
    }

    function _messageResponse(message) {
        if (message.method !== "message") {
            _centrifuge._debug('Unknown message', message);
            return;
        }

        if (message.body) {
            var body = $.parseJSON(message.body);
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

    function _addListener(channel, callback, isListener)
    {
        // The data structure is a map<channel, subscription[]>, where each subscription
        // holds the callback to be called and its scope.

        _centrifuge._debug('Adding', isListener ? 'listener' : 'subscription', 'on', channel);

        var subscription = {
            channel: channel,
            callback: callback,
            listener: isListener
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

        // For backward compatibility: we used to return [channel, subscription.id]
        //subscription[0] = channel;
        //subscription[1] = subscription.id;

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

            var subscribe_to = {};
            subscribe_to[category] = [channel];

            var centrifugeMessage = {
                "method": "subscribe",
                "params": {
                    "to": subscribe_to
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

            var unsubscribe_from = {};
            unsubscribe_from[category] = [channel];

            var centrifugeMessage = {
                "method": "unsubscribe",
                "params": {
                    "from": unsubscribe_from
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
            _publishCallback: publishCallback
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
            _presenceCallback: presenceCallback
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
            _historyCallback: historyCallback
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
};
