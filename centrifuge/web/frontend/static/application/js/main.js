(function($) {
    $.extend({
        centrifuge_main : function() {

            var defaults = {
                tab_prefix: "/tab_",
                max_tab_text_length: 10,
                max_events_amount: 50,
                project_tab: '_info',
                socket_url: '/socket',
                metrics_interval: 10000,
                global_tabs_element: '#tabs',
                info_template_element: '#info_template',
                transports: [
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

            var options = $.extend(defaults, {});

            var projects = [];
            var global_projects = {};

            // sock js connection
            var connection = null;

            try {
                // in Firefox esc key closes xhr and websocket connections
                // so we should prevent it to happen
                if (window.addEventListener) {
                    window.addEventListener('keydown', function(e) {
                        (e.keyCode == 27 && e.preventDefault());
                    });
                }
            } catch(e) {}

            var global_tabs = $(options.global_tabs_element);
            var global_info_template = $(options.info_template_element);

            // jsrender templates
            var event_template = $('#event_template');
            var tab_template = $('#tab_template');
            var tab_pane_template = $('#tab_pane_template');
            var node_info_row_template = $('#node_info_row_template');

            var node_count;
            var node_info;
            var node_info_loader;
            var node_timeouts = {};

            var project_settings_button = $('#project-settings');

            var show_hashed_tab = function() {
                var hash = document.location.hash;
                if (hash) {
                    global_tabs.find('a[href='+hash.replace(options.tab_prefix,"")+']').tab('show');
                }
            };

            var make_tab_text = function(name, display_name) {
                if (display_name === '' || !display_name) {
                    return name;
                }
                return display_name;
            };

            var get_active_tab_name = function() {
                var active_tab = global_tabs.find('li.active').find('[data-toggle="tab"]');
                return active_tab.attr('data-name');
            };

			var get_project_by_name = function(project_name) {
				if (!(project_name in global_projects)) {
					return null;
				}
				return global_projects[project_name];
			};

            var get_tab_for_project = function(project) {
                return $('#tab-'+ project['name']);
            };

            var get_content_for_project = function(project) {
                return $('#' + project['name']);
            };

            var prepare_html = function(html) {
                return html;
            };

            var get_project_event_counter = function(project) {
            	var project_name = project['name'];
                return $('#tab-' + project_name).find('.project-event-counter');
            };

            var get_project_event_counter_value = function(counter) {
                return parseInt(counter.text());
            };

            var set_project_event_counter_value = function(counter, value) {
                var prefix;
                if (typeof(value) === 'number' && value > 0) {
                    prefix = '+';
                } else {
                    prefix = '';
                }
                counter.html(prefix + value.toString());
            };

            var highlight_tab = function(project, enable) {
                var tab = get_tab_for_project(project);
                if (enable === true) {
                    tab.addClass('text-success');
                } else {
                    tab.removeClass('text-success');
                }
            };

            var clear_project_event_counter = function(project) {
                var counter = get_project_event_counter(project);
                set_project_event_counter_value(counter, 0);
                counter.addClass('hidden');
            };

            var incr_project_event_counter = function(project) {
                var new_value;
                var counter = get_project_event_counter(project);
                var current_value = get_project_event_counter_value(counter);
                if (Boolean(current_value)) {
                    new_value = current_value + 1;
                } else {
                    new_value = 1;
                }
                set_project_event_counter_value(counter, new_value);
                counter.removeClass('hidden');
            };

            var handle_node_info = function(data) {
                node_info_loader.remove();
                node_count.text(data['nodes']);
                var uid = data['uid'];
                var existing_row = node_info.find('#node-info-row-' + uid);
                var html = node_info_row_template.render(data);
                if (existing_row.length > 0) {
                    existing_row.replaceWith(html);
                } else {
                    node_info.append(html);
                }
                window.clearTimeout(node_timeouts[uid]);
                node_timeouts[uid] = window.setTimeout(function(){
                    var node_info_row = node_info.find('#node-info-row-' + uid);
                    if (node_info_row.length > 0) {
                        node_info_row.remove();
                        delete node_timeouts[uid];
                    }
                }, options.metrics_interval + 5000);
            };

            var handle_admin_message = function(message) {
                var type = message['type'];
                var data = message['data'];
                if (type === 'node') {
                    handle_node_info(data);
                }
            };

            var handle_event_message = function(data) {
                if (typeof data["admin"] != 'undefined') {
                    handle_admin_message(data);
                } else {
                    var event_id = data['message']['uid'];
                    var channel = data['message']['channel'];
                    var event_data = data['message']['data'];
                    var project_name = data['project'];
                    var project = get_project_by_name(project_name);
                    var active_tab_name = get_active_tab_name();
                    var tab = get_tab_for_project(project);

                    if (tab.length > 0) {
                        // tab already opened and meta already loaded
                        var container = get_content_for_project(project).find('.log');
                        render_event(container, project, event_id, channel, event_data);
                    } else {
                        if (active_tab_name !== options.project_tab) {
                            highlight_tab(global_projects[options.project_tab], true);
                        }
                    }
                    if (active_tab_name !== project_name) {
                        incr_project_event_counter(project);
                        highlight_tab(project, true);
                    }
                }
            };

            var connect = function() {
                disconnect();

                //noinspection JSUnresolvedFunction
                connection = new SockJS(window.location.protocol + '//' + window.location.host + options.socket_url, null, {
                    protocols_whitelist: options.transports
                });

                connection.onopen = function() {
                    $('.not-connected').hide();
                    $('.connected').show();
                };

                connection.onmessage = function(e) {
                    var body = $.parseJSON(e.data);
                    handle_event_message(body);
                };

                connection.onerror = function(e) {
                    console.log(e);
                };
                connection.onclose = function() {
                    connection = null;
                    window.setTimeout(function(){
                        $('.connected').hide();
                        $('.not-connected').show();
                        window.setTimeout(connect, 1000);
                    }, 3000);
                };
            };

            var disconnect = function() {
                if (connection != null) {
                    console.log('Disconnecting...');
                    connection.close();
                    connection = null;
                }
            };

            var create_socket_connection = function() {
                connect();
            };

            var show_event = function(event_id, fade) {
                var event_element = $('#event-' + event_id);
                if (fade === true) {
                    event_element.fadeIn();
                } else {
                    event_element.show();
                }
            };

            var pad = function (n) {
                // http://stackoverflow.com/a/3313953/1288429
                return ("0" + n).slice(-2);
            };

            var render_event = function(container, project, event_id, channel, event_data) {

                var d = new Date();

                var html = event_template.render({
                    'event_id': event_id,
                    'channel': channel,
                    'data': prettify_json(event_data),
                    'project': project,
                    'time': pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds())
                });

                var prepared_html = prepare_html(html);

                container.prepend(prepared_html);

                var fade = true;

                show_event(event_id, fade);

                container.find('.event:gt(' + options.max_events_amount + ')').remove();
            };

            var create_tab = function(project) {
                project['tab_text'] = make_tab_text(project['name'], project['display_name']);
                var tab_content = tab_pane_template.render(project);
                var tab_element = tab_template.render(project);
                $('#tab-content').append(tab_content);
                global_tabs.append(tab_element);
            };

			var route = function(tab) {
				var project_name = tab.attr('data-name');
                var project;
                if (project_name === options.project_tab) {
                    project = {"name": options.project_tab};
                } else {
                    project = get_project_by_name(project_name);
                }
                highlight_tab(project, false);
                if (project['name'] !== options.project_tab) {
                    project_settings_button.attr('href', '/project/' + project['name'] + '/credentials').show();
                    clear_project_event_counter(project);
                } else {
                    project_settings_button.hide();
                }
			};

            var initialize = function() {

                create_socket_connection();

                $.get("/info/", {}, function(data) {
                    projects = data.structure;
                    global_projects = data.structure_dict;
                    if (projects) {
                        for (var index in projects) {
                            //noinspection JSUnfilteredForInLoop
                            var project = projects[index];
                            create_tab(project);
                        }
                    }

                    var protocol = window.location.protocol;
                    var is_secure = false;
                    if (protocol === "https:") {
                        is_secure = true;
                    }
                    var sockjs_protocol = is_secure? "https://": "http://";
                    var websocket_protocol = is_secure? "wss://": "ws://";
                    data["sockjs_endpoint"] = sockjs_protocol + window.location.host + '/connection';
                    data["ws_endpoint"] = websocket_protocol + window.location.host + '/connection/websocket';
                    data["api_endpoint"] = sockjs_protocol + window.location.host + '/api';

                    var info_html = global_info_template.render(data);
                    $("#_info").append(info_html);

                    node_count = $('#node-count');
                    node_info = $('#node-info');
                    node_info_loader = $('#node-info-loader');
                    
                    show_hashed_tab();

                    // Change hash for page-reload
                    global_tabs.on('shown.bs.tab', 'a', function (e) {
                        window.location.hash = e.target.hash.replace("#", "#" + options.tab_prefix);
                        var self = $(this);
                        route(self);
                    });

                    if (!window.location.hash) {
                        global_tabs.find('a:first').tab('show');
                    } else {
                        var hash = window.location.hash;
                        var project_name = hash.replace('#' + options.tab_prefix, '');
                        var project_tab = global_tabs.find('[data-name="'+ project_name +'"]');
                        if (project_tab.length) {
                            route(project_tab);
                        } else {
                            global_tabs.find('a:first').tab('show');
                        }
                    }
                }, "json");

            };

            initialize();
        }
    })
})(jQuery);