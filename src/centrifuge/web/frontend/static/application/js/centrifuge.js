//noinspection ThisExpressionReferencesGlobalObjectJS
(function () {
    'use strict';

    /**
     * Oliver Caldwell
     * http://oli.me.uk/2013/06/01/prototypical-inheritance-done-right/
     */

    if (!Object.create) {
        Object.create = (function(){
            function F(){}

            return function(o){
                if (arguments.length != 1) {
                    throw new Error('Object.create implementation only accepts one parameter.');
                }
                F.prototype = o;
                return new F()
            }
        })()
    }

    if (!Array.prototype.indexOf) {
        Array.prototype.indexOf = function (searchElement /*, fromIndex */) {
            'use strict';
            if (this == null) {
                throw new TypeError();
            }
            var n, k, t = Object(this),
                len = t.length >>> 0;

            if (len === 0) {
                return -1;
            }
            n = 0;
            if (arguments.length > 1) {
                n = Number(arguments[1]);
                if (n != n) { // shortcut for verifying if it's NaN
                    n = 0;
                } else if (n != 0 && n != Infinity && n != -Infinity) {
                    n = (n > 0 || -1) * Math.floor(Math.abs(n));
                }
            }
            if (n >= len) {
                return -1;
            }
            for (k = n >= 0 ? n : Math.max(len - Math.abs(n), 0); k < len; k++) {
                if (k in t && t[k] === searchElement) {
                    return k;
                }
            }
            return -1;
        };
    }

    function extend(destination, source) {
        destination.prototype = Object.create(source.prototype);
        destination.prototype.constructor = destination;
        return source.prototype;
    }

    /**
     * EventEmitter v4.2.3 - git.io/ee
     * Oliver Caldwell
     * MIT license
     * @preserve
     */

    /**
     * Class for managing events.
     * Can be extended to provide event functionality in other classes.
     *
     * @class EventEmitter Manages event registering and emitting.
     */
    function EventEmitter() {}

    // Shortcuts to improve speed and size

    // Easy access to the prototype
    var proto = EventEmitter.prototype;

    /**
     * Finds the index of the listener for the event in it's storage array.
     *
     * @param {Function[]} listeners Array of listeners to search through.
     * @param {Function} listener Method to look for.
     * @return {Number} Index of the specified listener, -1 if not found
     * @api private
     */
    function indexOfListener(listeners, listener) {
        var i = listeners.length;
        while (i--) {
            if (listeners[i].listener === listener) {
                return i;
            }
        }

        return -1;
    }

    /**
     * Alias a method while keeping the context correct, to allow for overwriting of target method.
     *
     * @param {String} name The name of the target method.
     * @return {Function} The aliased method
     * @api private
     */
    function alias(name) {
        return function aliasClosure() {
            return this[name].apply(this, arguments);
        };
    }

    /**
     * Returns the listener array for the specified event.
     * Will initialise the event object and listener arrays if required.
     * Will return an object if you use a regex search. The object contains keys for each matched event. So /ba[rz]/ might return an object containing bar and baz. But only if you have either defined them with defineEvent or added some listeners to them.
     * Each property in the object response is an array of listener functions.
     *
     * @param {String|RegExp} evt Name of the event to return the listeners from.
     * @return {Function[]|Object} All listener functions for the event.
     */
    proto.getListeners = function getListeners(evt) {
        var events = this._getEvents();
        var response;
        var key;

        // Return a concatenated array of all matching events if
        // the selector is a regular expression.
        if (typeof evt === 'object') {
            response = {};
            for (key in events) {
                if (events.hasOwnProperty(key) && evt.test(key)) {
                    response[key] = events[key];
                }
            }
        }
        else {
            response = events[evt] || (events[evt] = []);
        }

        return response;
    };

    /**
     * Takes a list of listener objects and flattens it into a list of listener functions.
     *
     * @param {Object[]} listeners Raw listener objects.
     * @return {Function[]} Just the listener functions.
     */
    proto.flattenListeners = function flattenListeners(listeners) {
        var flatListeners = [];
        var i;

        for (i = 0; i < listeners.length; i += 1) {
            flatListeners.push(listeners[i].listener);
        }

        return flatListeners;
    };

    /**
     * Fetches the requested listeners via getListeners but will always return the results inside an object. This is mainly for internal use but others may find it useful.
     *
     * @param {String|RegExp} evt Name of the event to return the listeners from.
     * @return {Object} All listener functions for an event in an object.
     */
    proto.getListenersAsObject = function getListenersAsObject(evt) {
        var listeners = this.getListeners(evt);
        var response;

        if (listeners instanceof Array) {
            response = {};
            response[evt] = listeners;
        }

        return response || listeners;
    };

    /**
     * Adds a listener function to the specified event.
     * The listener will not be added if it is a duplicate.
     * If the listener returns true then it will be removed after it is called.
     * If you pass a regular expression as the event name then the listener will be added to all events that match it.
     *
     * @param {String|RegExp} evt Name of the event to attach the listener to.
     * @param {Function} listener Method to be called when the event is emitted. If the function returns true then it will be removed after calling.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.addListener = function addListener(evt, listener) {
        var listeners = this.getListenersAsObject(evt);
        var listenerIsWrapped = typeof listener === 'object';
        var key;

        for (key in listeners) {
            if (listeners.hasOwnProperty(key) && indexOfListener(listeners[key], listener) === -1) {
                listeners[key].push(listenerIsWrapped ? listener : {
                    listener: listener,
                    once: false
                });
            }
        }

        return this;
    };

    /**
     * Alias of addListener
     */
    proto.on = alias('addListener');

    /**
     * Semi-alias of addListener. It will add a listener that will be
     * automatically removed after it's first execution.
     *
     * @param {String|RegExp} evt Name of the event to attach the listener to.
     * @param {Function} listener Method to be called when the event is emitted. If the function returns true then it will be removed after calling.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.addOnceListener = function addOnceListener(evt, listener) {
        //noinspection JSValidateTypes
        return this.addListener(evt, {
            listener: listener,
            once: true
        });
    };

    /**
     * Alias of addOnceListener.
     */
    proto.once = alias('addOnceListener');

    /**
     * Defines an event name. This is required if you want to use a regex to add a listener to multiple events at once. If you don't do this then how do you expect it to know what event to add to? Should it just add to every possible match for a regex? No. That is scary and bad.
     * You need to tell it what event names should be matched by a regex.
     *
     * @param {String} evt Name of the event to create.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.defineEvent = function defineEvent(evt) {
        this.getListeners(evt);
        return this;
    };

    /**
     * Uses defineEvent to define multiple events.
     *
     * @param {String[]} evts An array of event names to define.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.defineEvents = function defineEvents(evts) {
        for (var i = 0; i < evts.length; i += 1) {
            this.defineEvent(evts[i]);
        }
        return this;
    };

    /**
     * Removes a listener function from the specified event.
     * When passed a regular expression as the event name, it will remove the listener from all events that match it.
     *
     * @param {String|RegExp} evt Name of the event to remove the listener from.
     * @param {Function} listener Method to remove from the event.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.removeListener = function removeListener(evt, listener) {
        var listeners = this.getListenersAsObject(evt);
        var index;
        var key;

        for (key in listeners) {
            if (listeners.hasOwnProperty(key)) {
                index = indexOfListener(listeners[key], listener);

                if (index !== -1) {
                    listeners[key].splice(index, 1);
                }
            }
        }

        return this;
    };

    /**
     * Alias of removeListener
     */
    proto.off = alias('removeListener');

    /**
     * Adds listeners in bulk using the manipulateListeners method.
     * If you pass an object as the second argument you can add to multiple events at once. The object should contain key value pairs of events and listeners or listener arrays. You can also pass it an event name and an array of listeners to be added.
     * You can also pass it a regular expression to add the array of listeners to all events that match it.
     * Yeah, this function does quite a bit. That's probably a bad thing.
     *
     * @param {String|Object|RegExp} evt An event name if you will pass an array of listeners next. An object if you wish to add to multiple events at once.
     * @param {Function[]} [listeners] An optional array of listener functions to add.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.addListeners = function addListeners(evt, listeners) {
        // Pass through to manipulateListeners
        return this.manipulateListeners(false, evt, listeners);
    };

    /**
     * Removes listeners in bulk using the manipulateListeners method.
     * If you pass an object as the second argument you can remove from multiple events at once. The object should contain key value pairs of events and listeners or listener arrays.
     * You can also pass it an event name and an array of listeners to be removed.
     * You can also pass it a regular expression to remove the listeners from all events that match it.
     *
     * @param {String|Object|RegExp} evt An event name if you will pass an array of listeners next. An object if you wish to remove from multiple events at once.
     * @param {Function[]} [listeners] An optional array of listener functions to remove.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.removeListeners = function removeListeners(evt, listeners) {
        // Pass through to manipulateListeners
        return this.manipulateListeners(true, evt, listeners);
    };

    /**
     * Edits listeners in bulk. The addListeners and removeListeners methods both use this to do their job. You should really use those instead, this is a little lower level.
     * The first argument will determine if the listeners are removed (true) or added (false).
     * If you pass an object as the second argument you can add/remove from multiple events at once. The object should contain key value pairs of events and listeners or listener arrays.
     * You can also pass it an event name and an array of listeners to be added/removed.
     * You can also pass it a regular expression to manipulate the listeners of all events that match it.
     *
     * @param {Boolean} remove True if you want to remove listeners, false if you want to add.
     * @param {String|Object|RegExp} evt An event name if you will pass an array of listeners next. An object if you wish to add/remove from multiple events at once.
     * @param {Function[]} [listeners] An optional array of listener functions to add/remove.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.manipulateListeners = function manipulateListeners(remove, evt, listeners) {
        var i;
        var value;
        var single = remove ? this.removeListener : this.addListener;
        var multiple = remove ? this.removeListeners : this.addListeners;

        // If evt is an object then pass each of it's properties to this method
        if (typeof evt === 'object' && !(evt instanceof RegExp)) {
            for (i in evt) {
                if (evt.hasOwnProperty(i) && (value = evt[i])) {
                    // Pass the single listener straight through to the singular method
                    if (typeof value === 'function') {
                        single.call(this, i, value);
                    }
                    else {
                        // Otherwise pass back to the multiple function
                        multiple.call(this, i, value);
                    }
                }
            }
        }
        else {
            // So evt must be a string
            // And listeners must be an array of listeners
            // Loop over it and pass each one to the multiple method
            i = listeners.length;
            while (i--) {
                single.call(this, evt, listeners[i]);
            }
        }

        return this;
    };

    /**
     * Removes all listeners from a specified event.
     * If you do not specify an event then all listeners will be removed.
     * That means every event will be emptied.
     * You can also pass a regex to remove all events that match it.
     *
     * @param {String|RegExp} [evt] Optional name of the event to remove all listeners for. Will remove from every event if not passed.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.removeEvent = function removeEvent(evt) {
        var type = typeof evt;
        var events = this._getEvents();
        var key;

        // Remove different things depending on the state of evt
        if (type === 'string') {
            // Remove all listeners for the specified event
            delete events[evt];
        }
        else if (type === 'object') {
            // Remove all events matching the regex.
            for (key in events) {
                //noinspection JSUnresolvedFunction
                if (events.hasOwnProperty(key) && evt.test(key)) {
                    delete events[key];
                }
            }
        }
        else {
            // Remove all listeners in all events
            delete this._events;
        }

        return this;
    };

    /**
     * Emits an event of your choice.
     * When emitted, every listener attached to that event will be executed.
     * If you pass the optional argument array then those arguments will be passed to every listener upon execution.
     * Because it uses `apply`, your array of arguments will be passed as if you wrote them out separately.
     * So they will not arrive within the array on the other side, they will be separate.
     * You can also pass a regular expression to emit to all events that match it.
     *
     * @param {String|RegExp} evt Name of the event to emit and execute listeners for.
     * @param {Array} [args] Optional array of arguments to be passed to each listener.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.emitEvent = function emitEvent(evt, args) {
        var listeners = this.getListenersAsObject(evt);
        var listener;
        var i;
        var key;
        var response;

        for (key in listeners) {
            if (listeners.hasOwnProperty(key)) {
                i = listeners[key].length;

                while (i--) {
                    // If the listener returns true then it shall be removed from the event
                    // The function is executed either with a basic call or an apply if there is an args array
                    listener = listeners[key][i];

                    if (listener.once === true) {
                        this.removeListener(evt, listener.listener);
                    }

                    response = listener.listener.apply(this, args || []);

                    if (response === this._getOnceReturnValue()) {
                        this.removeListener(evt, listener.listener);
                    }
                }
            }
        }

        return this;
    };

    /**
     * Alias of emitEvent
     */
    proto.trigger = alias('emitEvent');

    //noinspection JSValidateJSDoc,JSCommentMatchesSignature
    /**
     * Subtly different from emitEvent in that it will pass its arguments on to the listeners, as opposed to taking a single array of arguments to pass on.
     * As with emitEvent, you can pass a regex in place of the event name to emit to all events that match it.
     *
     * @param {String|RegExp} evt Name of the event to emit and execute listeners for.
     * @param {...*} Optional additional arguments to be passed to each listener.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.emit = function emit(evt) {
        var args = Array.prototype.slice.call(arguments, 1);
        return this.emitEvent(evt, args);
    };

    /**
     * Sets the current value to check against when executing listeners. If a
     * listeners return value matches the one set here then it will be removed
     * after execution. This value defaults to true.
     *
     * @param {*} value The new value to check for when executing listeners.
     * @return {Object} Current instance of EventEmitter for chaining.
     */
    proto.setOnceReturnValue = function setOnceReturnValue(value) {
        this._onceReturnValue = value;
        return this;
    };

    /**
     * Fetches the current value to check against when executing listeners. If
     * the listeners return value matches this one then it should be removed
     * automatically. It will return true by default.
     *
     * @return {*|Boolean} The current value to check for or the default, true.
     * @api private
     */
    proto._getOnceReturnValue = function _getOnceReturnValue() {
        if (this.hasOwnProperty('_onceReturnValue')) {
            return this._onceReturnValue;
        }
        else {
            return true;
        }
    };

    /**
     * Fetches the events object and creates one if required.
     *
     * @return {Object} The events storage object.
     * @api private
     */
    proto._getEvents = function _getEvents() {
        return this._events || (this._events = {});
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
        if (value === undefined || value === null) {
            return false;
        }
        return typeof value === 'string' || value instanceof String;
    }

    function isFunction(value) {
        if (value === undefined || value === null) {
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
        this._sep = ':';
        this._fullRegex = /^([^_]+[A-z0-9_@\-]{2,}):([A-z0-9_@\-\.]+)$/;
        this._channelOnlyRegex = /^([A-z0-9_@\-\.]+)$/;
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

    extend(Centrifuge, EventEmitter);

    var centrifuge_proto = Centrifuge.prototype;

    centrifuge_proto._debug = function () {
        if (this._config.debug === true) {
            log('debug', arguments);
        }
    };

    centrifuge_proto._configure = function (configuration) {
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

    centrifuge_proto._parsePath = function (path) {
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

    centrifuge_proto._makePath = function (namespace, channel) {
        if (namespace === '' || namespace === null || namespace == undefined) {
            if (!this._channelOnlyRegex.test(channel)) {
                throw "Invalid channel name " + channel;
            }
            return channel;
        }
        var path = namespace + this._sep + channel;
        if (!this._fullRegex.test(path)) {
            throw "Invalid path " + path;
        }
        return path;
    };

    centrifuge_proto._setStatus = function (newStatus) {
        if (this._status !== newStatus) {
            this._debug('Status', this._status, '->', newStatus);
            this._status = newStatus;
        }
    };

    centrifuge_proto._isDisconnected = function () {
        return this._isConnected() === false;
    };

    centrifuge_proto._isConnected = function () {
        return this._status === 'connected';
    };

    centrifuge_proto._nextMessageId = function () {
        return ++this._messageId;
    };

    centrifuge_proto._clearSubscriptions = function () {
        this._subscriptions = {};
    };

    centrifuge_proto._send = function (messages) {
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

    centrifuge_proto._connect = function (callback) {

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

        this._transport.onopen = function () {

            var centrifugeMessage = {
                'method': 'connect',
                'params': {
                    'token': self._config.token,
                    'user': self._config.user,
                    'project': self._config.project
                }
            };
            self._send([centrifugeMessage]);
        };

        this._transport.onerror = function (error) {
            this._debug(error);
        };

        this._transport.onclose = function () {
            self._setStatus('disconnected');
            self.trigger('disconnect');
            if (self._reconnect === true) {
                window.setTimeout(function () {
                    if (self._reconnect === true) {
                        self._connect.call(self)
                    }
                }, self._config.retry);
            }
        };

        this._transport.onmessage = function (event) {
            var data;
            if (self._sockjs === true) {
                data = event.data;
            } else {
                data = JSON.parse(event.data);
            }
            self._receive(data);
        };
    };

    centrifuge_proto._disconnect = function () {
        this._clientId = null;
        this._setStatus('disconnected');
        this._subscriptions = {};
        this._reconnect = false;
        this._transport.close();
    };

    centrifuge_proto._getSubscription = function (path) {
        var subscription = this._subscriptions[path];
        if (!subscription) {
            return null;
        }
        return subscription;
    };

    centrifuge_proto._findSubscription = function (namespace, channel) {
        var subscription;
        var path = this._makePath(namespace, channel);
        subscription = this._subscriptions[path];
        if (!subscription) {
            path = this._makePath(null, channel);
            subscription = this._subscriptions[path];
            if (!subscription) {
                return null;
            }
        }
        return subscription;
    };

    centrifuge_proto._removeSubscription = function (path) {
        try {
            delete this._subscriptions[path];
        } catch (e) {
            this._debug('nothing to delete for path ', path);
        }
    };

    centrifuge_proto._connectResponse = function (message) {
        if (message.error === null) {
            this._clientId = message.body;
            this._setStatus('connected');
            this.trigger('connect', [message]);
        } else {
            this.trigger('error', [message]);
            this.trigger('connect:error', [message]);
        }
    };

    centrifuge_proto._disconnectResponse = function (message) {
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

    centrifuge_proto._subscribeResponse = function (message) {
        var namespace = message.params["namespace"];
        var channel = message.params["channel"];
        var path = this._makePath(namespace, channel);
        var subscription = this._subscriptions[path];
        if (!subscription) {
            return;
        }
        if (message.error === null) {
            subscription.subscribed = true;
            subscription.trigger('subscribe:success', [message]);
            subscription.trigger('ready', [message]);
        } else {
            subscription.trigger('subscribe:error', [message]);
            subscription.trigger('error', [message]);
            this.trigger('error', [message]);
        }
    };

    centrifuge_proto._unsubscribeResponse = function (message) {
        if (message.error !== null) {
            this.trigger('error', [message]);
        }
    };

    centrifuge_proto._publishResponse = function (message) {
        var namespace = message.params["namespace"];
        var channel = message.params["channel"];
        var path = this._makePath(namespace, channel);
        var subscription = this._subscriptions[path];
        if (!subscription) {
            return;
        }
        if (message.error === null) {
            subscription.trigger('publish:success', [message]);
        } else {
            subscription.trigger('publish:error', [message]);
            this.trigger('error', [message]);
        }
    };

    centrifuge_proto._presenceResponse = function (message) {
        var namespace = message.body["namespace"];
        var channel = message.body["channel"];
        var subscription = this._findSubscription(namespace, channel);
        if (!subscription) {
            return;
        }
        if (message.error === null) {
            subscription.trigger('presence', [message.body]);
            subscription.trigger('presence:success', [message]);
        } else {
            subscription.trigger('presence:error', [message]);
            this.trigger('error', [message]);
        }
    };

    centrifuge_proto._historyResponse = function (message) {
        var namespace = message.body["namespace"];
        var channel = message.body["channel"];
        var subscription = this._findSubscription(namespace, channel);
        if (!subscription) {
            return;
        }
        if (message.error === null) {
            subscription.trigger('history', [message.body]);
            subscription.trigger('history:success', [message]);
        } else {
            subscription.trigger('history:error', [message]);
            this.trigger('error', [message]);
        }
    };

    centrifuge_proto._joinResponse = function(message) {
        if (message.body) {
            //noinspection JSValidateTypes
            var body = JSON.parse(message.body);
            var subscription = this._findSubscription(body.namespace, body.channel);
            if (!subscription) {
                return;
            }
            subscription.trigger('join', [body]);
        } else {
            this._debug('Unknown message', message);
        }
    };

    centrifuge_proto._leaveResponse = function(message) {
        if (message.body) {
            //noinspection JSValidateTypes
            var body = JSON.parse(message.body);
            var subscription = this._findSubscription(body.namespace, body.channel);
            if (!subscription) {
                return;
            }
            subscription.trigger('leave', [body]);
        } else {
            this._debug('Unknown message', message);
        }
    };

    centrifuge_proto._messageResponse = function (message) {
        if (message.body) {
            //noinspection JSValidateTypes
            var body = JSON.parse(message.body);
            var subscription = this._findSubscription(body.namespace, body.channel);
            if (!subscription) {
                return;
            }
            subscription.trigger('message', [body]);
        } else {
            this._debug('Unknown message', message);
        }
    };

    centrifuge_proto._receive = function (message) {

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
            case 'join':
                this._joinResponse(message);
                break;
            case 'leave':
                this._leaveResponse(message);
                break;
            case 'message':
                this._messageResponse(message);
                break;
            default:
                break;
        }
    };

    /* PUBLIC API */

    centrifuge_proto.getClientId = function () {
        return this._clientId;
    };

    centrifuge_proto.parsePath = centrifuge_proto._parsePath;

    centrifuge_proto.makePath = centrifuge_proto._makePath;

    centrifuge_proto.isConnected = centrifuge_proto._isConnected;

    centrifuge_proto.isDisconnected = centrifuge_proto._isDisconnected;

    centrifuge_proto.configure = function (configuration) {
        this._configure.call(this, configuration);
    };

    centrifuge_proto.connect = centrifuge_proto._connect;

    centrifuge_proto.disconnect = centrifuge_proto._disconnect;

    centrifuge_proto.getSubscription = centrifuge_proto._getSubscription;

    centrifuge_proto.findSubscription = centrifuge_proto._findSubscription;

    centrifuge_proto.send = function (message) {
        this._send([message]);
    };

    centrifuge_proto.subscribe = function (path, callback) {

        if (arguments.length < 1) {
            throw 'Illegal arguments number: required 1, got ' + arguments.length;
        }
        if (!isString(path)) {
            throw 'Illegal argument type: channel must be a string';
        }
        if (this.isDisconnected()) {
            throw 'Illegal state: already disconnected';
        }

        var current_subscription = this._getSubscription(path);

        if (current_subscription !== null) {
            return current_subscription;
        } else {
            var subscription = new Subscription(this, path);
            this._subscriptions[path] = subscription;
            subscription.subscribe(callback);
            return subscription;
        }
    };

    centrifuge_proto.unsubscribe = function (path) {
        if (arguments.length < 1) {
            throw 'Illegal arguments number: required 1, got ' + arguments.length;
        }
        if (!isString(path)) {
            throw 'Illegal argument type: channel must be a string';
        }
        if (this.isDisconnected()) {
            return;
        }

        var current_subscription = this._getSubscription(path);
        if (current_subscription !== null) {
            current_subscription.unsubscribe();
        }
    };

    centrifuge_proto.publish = function (path, data, callback) {
        var subscription = this.getSubscription(path);
        if (subscription === null) {
            this._debug("subscription not found for path " + path);
            return null;
        }
        subscription.publish(data, callback);
        return subscription;
    };

    centrifuge_proto.presence = function (path, callback) {
        var subscription = this.getSubscription(path);
        if (subscription === null) {
            this._debug("subscription not found for path " + path);
            return null;
        }
        subscription.presence(callback);
        return subscription;
    };

    centrifuge_proto.history = function (path, callback) {
        var subscription = this.getSubscription(path);
        if (subscription === null) {
            this._debug("subscription not found for path " + path);
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
        this.subscribed = false;
    }

    extend(Subscription, EventEmitter);

    var sub_proto = Subscription.prototype;

    sub_proto.getPath = function () {
        return this._path;
    };

    sub_proto.getCentrifuge = function () {
        return this._centrifuge;
    };

    sub_proto.parsePath = function () {
        return this._centrifuge.parsePath(this._path);
    };

    sub_proto.subscribe = function (callback) {
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
        this._centrifuge.send(centrifugeMessage);
        if (callback) {
            this.on('message', callback);
        }
    };

    sub_proto.unsubscribe = function () {
        this.subscribed = false;
        this._centrifuge._removeSubscription(this._path);
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
        this._centrifuge.send(centrifugeMessage);
    };

    sub_proto.publish = function (data, callback) {
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
        this._centrifuge.send(centrifugeMessage);
    };

    sub_proto.presence = function (callback) {
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
        this._centrifuge.send(centrifugeMessage);
    };

    sub_proto.history = function (callback) {
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
        this._centrifuge.send(centrifugeMessage);
    };

    // Expose the class either via AMD, CommonJS or the global object
    if (typeof define === 'function' && define.amd) {
        define(function () {
            return Centrifuge;
        });
    } else if (typeof module === 'object' && module.exports) {
        //noinspection JSUnresolvedVariable
        module.exports = Centrifuge;
    } else {
        //noinspection JSUnusedGlobalSymbols
        this.Centrifuge = Centrifuge;
    }

}.call(this));
