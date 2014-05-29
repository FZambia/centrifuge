/**
 * Centrifuge javascript DOM jQuery plugin
 * v0.5.1
 */
;(function (jQuery) {
    jQuery.extend({
        centrifuge_dom: function (custom_options) {

            var defaults = {
                url: null,
                selector: '.centrifuge',
                urlSelector: '#centrifuge-address',
                tokenSelector: '#centrifuge-token',
                projectSelector: '#centrifuge-project',
                userSelector: '#centrifuge-user',
                timestampSelector: '#centrifuge-timestamp',
                infoSelector: '#centrifuge-info',
                valueAttrName: 'data-centrifuge-value',
                channelAttr: 'data-centrifuge-channel',
                messageEventNameAttr: 'data-centrifuge-message',
                eventPrefix: 'centrifuge.',
                fullMessage: true,
                debug: false
            };

            var options = jQuery.extend(defaults, custom_options);

            var compliance = {};

            var handlers = jQuery(options.selector);

            function debug(message) {
                if (options.debug === true) {
                    console.log(message);
                }
            }

            function get_object_size(obj) {
                var size = 0, key;
                for (key in obj) {
                    if (obj.hasOwnProperty(key)) size++;
                }
                return size;
            }

            function get_message_data(message) {
                if (options.fullMessage === false) {
                    return message.data;
                }
                return message;
            }

            function get_message_body(message) {
                if (options.fullMessage === false) {
                    return message.body;
                }
                return message;
            }

            function get_message_error(message) {
                if (options.fullMessage === false) {
                    return message.error;
                }
                return message;
            }

            function get_handler_subscription(handler, centrifuge) {
                var handler_channel = handler.attr(options.channelAttr);
                var subscription = centrifuge.getSubscription(handler_channel);
                if (subscription === null) {
                    debug('no subscription found for channel ' + handler_channel);
                }
                return subscription;
            }

            function bind_centrifuge_events(centrifuge) {

                centrifuge.on('connect', function () {
                    debug("connected to Centrifuge");
                    subscribe(centrifuge);
                });

                centrifuge.on('error', function (err) {
                    debug(err);
                });

                centrifuge.on('disconnect', function () {
                    debug("disconnected from Centrifuge");
                    disconnect();
                });

            }

            function bind_handler_events(centrifuge) {

                handlers.on(options.eventPrefix + 'publish', function(data) {
                    // publish data into channel
                    var handler = $(this);
                    var subscription = get_handler_subscription(handler, centrifuge);
                    if (subscription) {
                        subscription.publish(data);
                    }
                });

                handlers.on(options.eventPrefix + 'presence', function() {
                    var handler = $(this);
                    var subscription = get_handler_subscription(handler, centrifuge);
                    if (subscription) {
                        subscription.presence(function(message) {
                            handler.trigger('centrifuge-presence-message', get_message_data(message));
                        });
                    }
                });

                handlers.on(options.eventPrefix + 'history', function() {
                    var handler = $(this);
                    var subscription = get_handler_subscription(handler, centrifuge);
                    if (subscription) {
                        subscription.history(function(message) {
                            handler.trigger('centrifuge-history-message', get_message_data(message));
                        });
                    }
                });

                handlers.on(options.eventPrefix + 'unsubscribe', function() {
                    var handler = $(this);
                    var subscription = get_handler_subscription(handler, centrifuge);
                    if (subscription) {
                        subscription.unsubscribe();
                    }
                });

            }

            function handle_subscription(path, centrifuge) {

                var handler = compliance[path];

                var subscription = centrifuge.subscribe(path, function (message) {
                    debug(message);
                    var handler_event = handler.attr(options.messageEventNameAttr);
                    var message_event_name = options.eventPrefix + (handler_event || 'message');
                    handler.trigger(message_event_name, get_message_data(message));
                });

                subscription.on('subscribe:success', function(message) {
                    var subscribe_success_event_name = options.eventPrefix + 'subscribe:success';
                    handler.trigger(subscribe_success_event_name, get_message_body(message));
                });

                subscription.on('subscribe:error', function(message) {
                    debug(message);
                    var subscribe_success_event_name = options.eventPrefix + 'subscribe:error';
                    handler.trigger(subscribe_success_event_name, get_message_error(message));
                });

                subscription.on('join', function(message) {
                    debug(message);
                    var join_event_name = options.eventPrefix + 'join';
                    handler.trigger(join_event_name, get_message_data(message));
                });

                subscription.on('leave', function(message) {
                    debug(message);
                    var leave_event_name = options.eventPrefix + 'leave';
                    handler.trigger(leave_event_name, get_message_data(message));
                });

            }

            function handle_disconnect(path) {
                var handler = compliance[path];
                handler.trigger(options.eventPrefix + 'disconnect');
            }

            function subscribe(centrifuge) {
                for (var subscription_path in compliance) {
                    //noinspection JSUnfilteredForInLoop
                    handle_subscription(subscription_path, centrifuge);
                }
            }

            function disconnect() {
                for (var subscription_path in compliance) {
                    //noinspection JSUnfilteredForInLoop
                    handle_disconnect(subscription_path);
                }
            }

            function parse_dom(centrifuge) {
                handlers.each(function (index, element) {
                    var handler = jQuery(element);
                    var handler_channel = handler.attr(options.channelAttr);
                    compliance[handler_channel] = handler;
                });
            }

            function init() {

                if (!Centrifuge) {
                    console.log("No Centrifuge javascript client found");
                    return;
                }

                if (handlers.length === 0) {
                    debug("No Centrifuge handlers found on this page, nothing to do");
                    return;
                }

                var token = $(options.tokenSelector).attr(options.valueAttrName);
                if (!token) {
                    console.log("Centrifuge token not found");
                    return;
                }

                var project = $(options.projectSelector).attr(options.valueAttrName);
                if (!project) {
                    console.log("Centrifuge project not found");
                    return;
                }

                var user = $(options.userSelector).attr(options.valueAttrName);
                if (!user) {
                    console.log("Centrifuge user not found");
                    return;
                }

                var timestamp = $(options.timestampSelector).attr(options.valueAttrName);
                if (!timestamp) {
                    console.log("Centrifuge timestamp not found");
                    return;
                }

                var url;
                if (options.url === null) {
                    url = $(options.urlSelector).attr(options.valueAttrName);
                }

                if (!url) {
                    console.log("Centrifuge connection url not found");
                    return;
                }

                var info = $(options.infoSelector).attr(options.valueAttrName);
                if (!info) {
                    debug("Centrifuge info not used, token must be generated without info part.");
                    info = null;
                }

                //noinspection JSUnresolvedFunction
                var centrifuge = new Centrifuge({
                    url: url,
                    token: token,
                    project: project,
                    user: user,
                    timestamp: timestamp,
                    info: info
                });

                parse_dom(centrifuge);

                if (get_object_size(compliance) === 0) {
                    debug("No valid handlers found on page, no need in connection to Centrifuge");
                    return;
                }

                bind_centrifuge_events(centrifuge);
                bind_handler_events(centrifuge);
                centrifuge.connect();
            }

            return init();

        }
    });
})(jQuery);
