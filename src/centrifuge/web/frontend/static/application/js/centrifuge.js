/*
This is a modified version of Cometd (http://cometdproject.dojotoolkit.org/) javascript client
adapted for Centrifuge.

Original implementation can be found here:
https://github.com/cometd/cometd/blob/master/cometd-javascript/common/src/main/js/org/cometd/CometD.js

IMPLEMENTATION NOTES:
Be very careful in not changing the function order and pass this file every time through JSLint (http://jslint.com)
The only implied globals must be "dojo", "org" and "window", and check that there are no "unused" warnings
Failing to pass JSLint may result in shrinkers/minifiers to create an unusable file.
*/

centrifuge = function(name) {
    /**
     * The constructor for a centrifuge object, identified by an optional name.
     * The default name is the string 'default'.
     * @param name the optional name of this centrifuge object
     */
    var _centrifuge = this;
    var _name = name || 'default';
    var _status = 'disconnected';
    var _transport;
    var _messageId = 0;
    var _clientId = null;
    var _messageQueue = [];
    var _listeners = {};
    var _backoff = 0;
    var _handshakeProps;
    var _publishCallbacks = {};
    var _reestablish = false;
    var _connected = false;
    var _config = {
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
        try
        {
            return object[name];
        }
        catch (x)
        {
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
        for (var i = 2; i < arguments.length; ++i)
        {
            var object = arguments[i];

            if (object === undefined || object === null)
            {
                continue;
            }

            for (var propName in object)
            {
                //noinspection JSUnfilteredForInLoop
                var prop = _fieldValue(object, propName);
                //noinspection JSUnfilteredForInLoop
                var targ = _fieldValue(result, propName);

                // Avoid infinite loops
                if (prop === target)
                {
                    continue;
                }
                // Do not mixin undefined values
                if (prop === undefined)
                {
                    continue;
                }

                if (deep && typeof prop === 'object' && prop !== null)
                {
                    if (prop instanceof Array)
                    {
                        //noinspection JSUnfilteredForInLoop
                        result[propName] = this._mixin(deep, targ instanceof Array ? targ : [], prop);
                    }
                    else
                    {
                        var source = typeof targ === 'object' && !(targ instanceof Array) ? targ : {};
                        //noinspection JSUnfilteredForInLoop
                        result[propName] = this._mixin(deep, source, prop);
                    }
                }
                else
                {
                    //noinspection JSUnfilteredForInLoop
                    result[propName] = prop;
                }
            }
        }

        return result;
    };

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

    function _configure(configuration) {
        _centrifuge._debug('Configuring centrifuge object with', configuration);

        if (!configuration) {
            configuration = {};
        }

        _config = _centrifuge._mixin(false, _config, configuration);

        if (!_config.url) {
            throw 'Missing required configuration parameter \'url\' specifying the Centrifuge server URL';
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
    }

    // Needed to break cyclic dependencies between function definitions
    var _handleMessages;
    var _handleFailure;

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
            if (_isFunction(message._callback))
            {
                callback = message._callback;
                // Remove the publish callback before calling the extensions
                delete message._callback;
            }

            if (message !== undefined && message !== null)
            {
                messages[i] = message;
                if (callback)
                    _publishCallbacks[message.uid] = callback;
            }
            else
            {
                messages.splice(i--, 1);
            }
        }

        if (messages.length === 0)
        {
            return;
        }

        var url = _config.url;

        //noinspection JSUnusedGlobalSymbols
        var envelope = {
            url: url,
            messages: messages,
            onSuccess: function(rcvdMessages)
            {
                try
                {
                    _handleMessages.call(_centrifuge, rcvdMessages);
                }
                catch (x)
                {
                    _centrifuge._debug('Exception during handling of messages', x);
                }
            },
            onFailure: function(conduit, messages, failure)
            {
                try
                {
                    failure.connectionType = _centrifuge.getTransport().getType();
                    _handleFailure.call(_centrifuge, conduit, messages, failure);
                }
                catch (x)
                {
                    _centrifuge._debug('Exception during handling of failure', x);
                }
            }
        };
        _centrifuge._debug('Send', envelope);
        _transport.send(envelope);
    }

    function _queueSend(message)
    {
        _send([message]);
    }

    /**
     * Sends a complete bayeux message.
     * This method is exposed as a public so that extensions may use it
     * to send bayeux message directly, for example in case of re-sending
     * messages that have already been sent but that for some reason must
     * be resent.
     */
    this.send = _queueSend;

    function _resetBackoff()
    {
        _backoff = 0;
    }

    function _increaseBackoff()
    {
        if (_backoff < _config.maxBackoff)
        {
            _backoff += _config.backoffIncrement;
        }
    }

    /**
     * Sends the connect message
     */
    function _connect()
    {
        if (!_isDisconnected())
        {
            var message = {
                channel: '/meta/connect',
                connectionType: _transport.getType()
            };

            // In case of reload or temporary loss of connection
            // we want the next successful connect to return immediately
            // instead of being held by the server, so that connect listeners
            // can be notified that the connection has been re-established
            if (!_connected)
            {
                message.advice = { timeout: 0 };
            }

            _setStatus('connecting');
            _centrifuge._debug('Connect sent', message);
            _send([message]);
            _setStatus('connected');
        }
    }

    function _disconnect(abort)
    {
        if (abort)
        {
            _transport.abort();
        }
        _clientId = null;
        _setStatus('disconnected');
        _resetBackoff();

        // Fail any existing queued message
        if (_messageQueue.length > 0)
        {
            _handleFailure.call(_centrifuge, undefined, _messageQueue, {
                reason: 'Disconnected'
            });
            _messageQueue = [];
        }
    }

    /**
     * Sends the initial handshake message
     */
    function _handshake(handshakeProps)
    {
        _clientId = null;

        _clearSubscriptions();

        // Save the properties provided by the user, so that
        // we can reuse them during automatic re-handshake
        _handshakeProps = handshakeProps;

        var version = '1.0';

        var bayeuxMessage = {
            version: version,
            minimumVersion: '0.9',
            channel: '/meta/handshake'
        };
        // Do not allow the user to mess with the required properties,
        // so merge first the user properties and *then* the bayeux message
        var message = _centrifuge._mixin(false, {}, _handshakeProps, bayeuxMessage);

        // We started a batch to hold the application messages,
        // so here we must bypass it and send immediately.
        _setStatus('handshaking');
        _centrifuge._debug('Handshake sent', message);
        _send([message]);
    }

    function _failHandshake(message)
    {
        _notifyListeners('/meta/handshake', message);
        _notifyListeners('/meta/unsuccessful', message);
    }

    function _handshakeResponse(message)
    {
        if (message.error === null)
        {
            // Save clientId, figure out transport, then follow the advice to connect
            _clientId = message.clientId;

            // Here the new transport is in place, as well as the clientId, so
            // the listeners can perform a publish() if they want.
            // Notify the listeners before the connect below.
            message.reestablish = _reestablish;
            _reestablish = true;
            _notifyListeners('/meta/handshake', message);
        }
        else
        {
            _failHandshake(message);
        }
    }

    function _handshakeFailure(failure)
    {
        _failHandshake({
            successful: false,
            failure: failure,
            channel: '/meta/handshake',
            advice: {
                reconnect: 'retry',
                interval: _backoff
            }
        });
    }

    function _failConnect(message)
    {
        // Notify the listeners after the status change but before the next action
        _notifyListeners('/meta/connect', message);
        _notifyListeners('/meta/unsuccessful', message);
    }

    function _connectResponse(message)
    {
        _connected = message.successful;

        if (_connected)
        {
            _notifyListeners('/meta/connect', message);
        }
        else
        {
            _failConnect(message);
        }
    }

    function _connectFailure(failure)
    {
        _connected = false;
        _failConnect({
            successful: false,
            failure: failure,
            channel: '/meta/connect',
            advice: {
                reconnect: 'retry',
                interval: _backoff
            }
        });
    }

    function _failDisconnect(message)
    {
        _disconnect(true);
        _notifyListeners('/meta/disconnect', message);
        _notifyListeners('/meta/unsuccessful', message);
    }

    function _disconnectResponse(message)
    {
        if (message.error === null)
        {
            _disconnect(false);
            _notifyListeners('/meta/disconnect', message);
        }
        else
        {
            _failDisconnect(message);
        }
    }

    function _disconnectFailure(failure)
    {
        _failDisconnect({
            successful: false,
            failure: failure,
            channel: '/meta/disconnect',
            advice: {
                reconnect: 'none',
                interval: 0
            }
        });
    }

    function _failSubscribe(message)
    {
        _notifyListeners('/meta/subscribe', message);
        _notifyListeners('/meta/unsuccessful', message);
    }

    function _subscribeResponse(message)
    {
        if (message.error === null)
        {
            _notifyListeners('/meta/subscribe', message);
        }
        else
        {
            _failSubscribe(message);
        }
    }

    function _subscribeFailure(failure)
    {
        _failSubscribe({
            successful: false,
            failure: failure,
            channel: '/meta/subscribe',
            advice: {
                reconnect: 'none',
                interval: 0
            }
        });
    }

    function _failUnsubscribe(message)
    {
        _notifyListeners('/meta/unsubscribe', message);
        _notifyListeners('/meta/unsuccessful', message);
    }

    function _unsubscribeResponse(message)
    {
        if (message.error === null)
        {
            _notifyListeners('/meta/unsubscribe', message);
        }
        else
        {
            _failUnsubscribe(message);
        }
    }

    function _unsubscribeFailure(failure)
    {
        _failUnsubscribe({
            successful: false,
            failure: failure,
            channel: '/meta/unsubscribe',
            advice: {
                reconnect: 'none',
                interval: 0
            }
        });
    }

    function _handlePublishCallback(message)
    {
        var callback = _publishCallbacks[message.uid];
        if (_isFunction(callback))
        {
            delete _publishCallbacks[message.uid];
            callback.call(_centrifuge, message);
        }
    }

    function _failMessage(message)
    {
        _handlePublishCallback(message);
        _notifyListeners('/meta/publish', message);
        _notifyListeners('/meta/unsuccessful', message);
    }

    function _messageResponse(message)
    {
        if (message.error === null)
        {
            _handlePublishCallback(message);
            _notifyListeners('/meta/publish', message);
        }
        else
        {
            _failMessage(message);
        }
    }

    function _messageFailure(message, failure)
    {
        _failMessage({
            successful: false,
            failure: failure,
            channel: message.channel,
            advice: {
                reconnect: 'none',
                interval: 0
            }
        });
    }

    function _receive(message)
    {
        if (message === undefined || message === null)
        {
            return;
        }

        var channel = message.channel;
        switch (channel)
        {
            case '/meta/handshake':
                _handshakeResponse(message);
                break;
            case '/meta/connect':
                _connectResponse(message);
                break;
            case '/meta/disconnect':
                _disconnectResponse(message);
                break;
            case '/meta/subscribe':
                _subscribeResponse(message);
                break;
            case '/meta/unsubscribe':
                _unsubscribeResponse(message);
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

    _handleMessages = function(rcvdMessages)
    {
        _centrifuge._debug('Received', rcvdMessages);

        for (var i = 0; i < rcvdMessages.length; ++i)
        {
            var message = rcvdMessages[i];
            _receive(message);
        }
    };

    _handleFailure = function(conduit, messages, failure)
    {
        _centrifuge._debug('handleFailure', conduit, messages, failure);

        for (var i = 0; i < messages.length; ++i)
        {
            var message = messages[i];
            var messageFailure = _centrifuge._mixin(false, { message: message, transport: conduit }, failure);
            var channel = message.channel;
            switch (channel)
            {
                case '/meta/handshake':
                    _handshakeFailure(messageFailure);
                    break;
                case '/meta/connect':
                    _connectFailure(messageFailure);
                    break;
                case '/meta/disconnect':
                    _disconnectFailure(messageFailure);
                    break;
                case '/meta/subscribe':
                    _subscribeFailure(messageFailure);
                    break;
                case '/meta/unsubscribe':
                    _unsubscribeFailure(messageFailure);
                    break;
                default:
                    _messageFailure(message, messageFailure);
                    break;
            }
        }
    };

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

    function _resolveScopedCallback(scope, callback)
    {
        var delegate = {
            scope: scope,
            method: callback
        };
        if (_isFunction(scope))
        {
            delegate.scope = undefined;
            delegate.method = scope;
        }
        else
        {
            if (_isString(callback))
            {
                if (!scope)
                {
                    throw 'Invalid scope ' + scope;
                }
                delegate.method = scope[callback];
                if (!_isFunction(delegate.method))
                {
                    throw 'Invalid callback ' + callback + ' for scope ' + scope;
                }
            }
            else if (!_isFunction(callback))
            {
                throw 'Invalid callback ' + callback;
            }
        }
        return delegate;
    }

    function _addListener(channel, scope, callback, isListener)
    {
        // The data structure is a map<channel, subscription[]>, where each subscription
        // holds the callback to be called and its scope.

        var delegate = _resolveScopedCallback(scope, callback);
        _centrifuge._debug('Adding', isListener ? 'listener' : 'subscription', 'on', channel, 'with scope', delegate.scope, 'and callback', delegate.method);

        var subscription = {
            channel: channel,
            scope: delegate.scope,
            callback: delegate.method,
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
        subscription[0] = channel;
        subscription[1] = subscription.id;

        return subscription;
    }

    //
    // PUBLIC API
    //

    /**
     * Configures the initial Bayeux communication with the Bayeux server.
     * Configuration is passed via an object that must contain a mandatory field <code>url</code>
     * of type string containing the URL of the Bayeux server.
     * @param configuration the configuration object
     */
    this.configure = function(configuration)
    {
        _configure.call(this, configuration);
    };

    /**
     * Establishes the Bayeux communication with the Bayeux server
     * via a handshake and a subsequent connect.
     * @param handshakeProps an object to be merged with the handshake message
     */
    this.handshake = function(handshakeProps)
    {
        _setStatus('disconnected');
        _reestablish = false;
        _handshake(handshakeProps);
    };

    /**
     * Disconnects from the Bayeux server.
     */
    this.disconnect = function()
    {
        if (_isDisconnected())
        {
            return;
        }

        var bayeuxMessage = {
            channel: '/meta/disconnect'
        };
        var message = this._mixin(false, {}, bayeuxMessage);
        _setStatus('disconnecting');
        _send([message]);
    };

    /**
     * Adds a listener for bayeux messages, performing the given callback in the given scope
     * when a message for the given channel arrives.
     * @param channel the channel the listener is interested to
     * @param scope the scope of the callback, may be omitted
     * @param callback the callback to call when a message is sent to the channel
     * @returns the subscription handle to be passed to {@link #removeListener(object)}
     * @see #removeListener(subscription)
     */
    this.addListener = function(channel, scope, callback)
    {
        if (arguments.length < 2)
        {
            throw 'Illegal arguments number: required 2, got ' + arguments.length;
        }
        if (!_isString(channel))
        {
            throw 'Illegal argument type: channel must be a string';
        }

        return _addListener(channel, scope, callback, true);
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
     * @param channel the channel to subscribe to
     * @param scope the scope of the callback, may be omitted
     * @param callback the callback to call when a message is sent to the channel
     * @param subscribeProps an object to be merged with the subscribe message
     * @return the subscription handle to be passed to {@link #unsubscribe(object)}
     */
    this.subscribe = function(channel, scope, callback, subscribeProps)
    {
        if (arguments.length < 2)
        {
            throw 'Illegal arguments number: required 2, got ' + arguments.length;
        }
        if (!_isString(channel))
        {
            throw 'Illegal argument type: channel must be a string';
        }
        if (_isDisconnected())
        {
            throw 'Illegal state: already disconnected';
        }

        // Normalize arguments
        if (_isFunction(scope))
        {
            subscribeProps = callback;
            callback = scope;
            scope = undefined;
        }

        // Only send the message to the server if this client has not yet subscribed to the channel
        var send = !_hasSubscriptions(channel);

        var subscription = _addListener(channel, scope, callback, false);

        if (send)
        {
            // Send the subscription message after the subscription registration to avoid
            // races where the server would send a message to the subscribers, but here
            // on the client the subscription has not been added yet to the data structures
            var bayeuxMessage = {
                channel: '/meta/subscribe',
                subscription: channel
            };
            var message = this._mixin(false, {}, subscribeProps, bayeuxMessage);
            _queueSend(message);
        }

        return subscription;
    };

    /**
     * Unsubscribes the subscription obtained with a call to {@link #subscribe(string, object, function)}.
     * @param subscription the subscription to unsubscribe.
     * @param unsubscribeProps an object to be merged with the unsubscribe message
     */
    this.unsubscribe = function(subscription, unsubscribeProps)
    {
        if (arguments.length < 1)
        {
            throw 'Illegal arguments number: required 1, got ' + arguments.length;
        }
        if (_isDisconnected())
        {
            throw 'Illegal state: already disconnected';
        }

        // Remove the local listener before sending the message
        // This ensures that if the server fails, this client does not get notifications
        this.removeListener(subscription);

        var channel = subscription.channel;
        // Only send the message to the server if this client unsubscribes the last subscription
        if (!_hasSubscriptions(channel))
        {
            var bayeuxMessage = {
                channel: '/meta/unsubscribe',
                subscription: channel
            };
            var message = this._mixin(false, {}, unsubscribeProps, bayeuxMessage);
            _queueSend(message);
        }
    };

    //noinspection JSUnusedGlobalSymbols
    this.resubscribe = function(subscription, subscribeProps)
    {
        _removeSubscription(subscription);
        if (subscription)
        {
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
     * @param channel the channel to publish the message to
     * @param content the content of the message
     * @param publishProps an object to be merged with the publish message
     * @param publishCallback a function to be invoked when the publish is acknowledged by the server
     */
    this.publish = function(channel, content, publishProps, publishCallback)
    {
        if (arguments.length < 1)
        {
            throw 'Illegal arguments number: required 1, got ' + arguments.length;
        }
        if (!_isString(channel))
        {
            throw 'Illegal argument type: channel must be a string';
        }
        if (_isDisconnected())
        {
            throw 'Illegal state: already disconnected';
        }

        if (_isFunction(content))
        {
            publishCallback = content;
            content = publishProps = {};
        }
        else if (_isFunction(publishProps))
        {
            publishCallback = publishProps;
            publishProps = {};
        }

        var bayeuxMessage = {
            channel: channel,
            data: content,
            _callback: publishCallback
        };
        var message = this._mixin(false, {}, publishProps, bayeuxMessage);
        _queueSend(message);
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Returns a string representing the status of the bayeux communication with the Bayeux server.
     */
    this.getStatus = function()
    {
        return _status;
    };

    /**
     * Returns whether this instance has been disconnected.
     */
    this.isDisconnected = _isDisconnected;

    /**
     * Sets the backoff period used to increase the backoff time when retrying an unsuccessful or failed message.
     * Default value is 1 second, which means if there is a persistent failure the retries will happen
     * after 1 second, then after 2 seconds, then after 3 seconds, etc. So for example with 15 seconds of
     * elapsed time, there will be 5 retries (at 1, 3, 6, 10 and 15 seconds elapsed).
     * @param period the backoff period to set
     * @see #getBackoffIncrement()
     */
    this.setBackoffIncrement = function(period)
    {
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
     * Returns the clientId assigned by the Bayeux server during handshake.
     */
    this.getClientId = function()
    {
        return _clientId;
    };

    //noinspection JSUnusedGlobalSymbols
    /**
     * Returns the URL of the Bayeux server.
     */
    this.getURL = function()
    {
        return _config.url;
    };

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
