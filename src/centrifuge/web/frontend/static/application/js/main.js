function prettify(json) {
    return syntaxHighlight(JSON.stringify(json, undefined, 4));
}

function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        var cls = 'number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'key';
            } else {
                cls = 'string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'boolean';
        } else if (/null/.test(match)) {
            cls = 'null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}

(function($) {
    $.extend({
        centrifuge_main : function(custom_options) {

            var defaults = {
                tab_prefix: "/tab_",
                max_tab_text_length: 10,
                max_events_amount: 100,
                current_user: {},
                project_tab: '_projects',
                projects: [],
                namespaces: {},
                socket_url: '/socket',
                global_content_element: '#main-content',
                global_tabs_element: '#tabs',
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

            var options = $.extend(defaults, custom_options);

            // sock js connection
            var connection = null;

            // in Firefox esc key closes xhr and websocket connections
            // so we should prevent it to happen
            if (window.addEventListener) {
                window.addEventListener('keydown', function(e) {
                    (e.keyCode == 27 && e.preventDefault());
                });
            }

			// set all event handlers on this element
            var global_content = $(options.global_content_element);

            var global_tabs = $(options.global_tabs_element);

			var global_projects = {};

            for (var index in options.projects) {
            	//noinspection JSUnfilteredForInLoop
                var project = options.projects[index];

                var project_id = project['_id'];

                global_projects[project_id] = project;

            }

            global_projects[options.project_tab] = {
                '_id': options.project_tab,
                'name': options.project_tab
            };

            // jsrender templates
            var event_template = $('#event_template');
            var project_template = $('#project_template');
            var tab_template = $('#tab_template');
            var tab_pane_template = $('#tab_pane_template');

            var show_hashed_tab = function() {
                var hash = document.location.hash;
                if (hash) {
                    global_tabs.find('a[href='+hash.replace(options.tab_prefix,"")+']').tab('show');
                }
            };

            var clear_element_content = function(element) {
                element.find('*').remove();
            };

            var make_tab_text = function(name) {
                if (name.length > options.max_tab_text_length) {
                    return name.toString().slice(0, options.max_tab_text_length) + '...';
                }
                return name;
            };

            var get_active_tab_id = function() {
                var active_tab = global_tabs.find('li.active').find('[data-toggle="tab"]');
                return active_tab.attr('data-id');
            };

			var get_project_by_id = function(project_id) {
				if (!(project_id in global_projects)) {
					return null;
				}
				return global_projects[project_id];
			};

            var get_tab_for_project = function(project) {
                return $('#tab-'+ project['_id']);
            };

            var get_content_for_project = function(project) {
                return $('#' + project['name']);
            };

            var get_current_user_id = function() {
                return options.current_user['_id'];
            };

            var prepare_html = function(html) {
                return html;
            };

            var get_project_event_counter = function(project) {
            	var project_id = project['_id'];
                return $('#project-' + project_id).find('.project-event-counter');
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

            var highlight_counter = function(counter, enable) {
                if (enable === true) {
                    counter.parents('.pill:first').removeClass('pill-info').addClass('pill-success').find('i').removeClass('text-info').addClass('text-success');
                } else {
                    counter.parents('.pill:first').removeClass('pill-success').addClass('pill-info').find('i').removeClass('text-success').addClass('text-info');
                }
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
                highlight_counter(counter, false);
                set_project_event_counter_value(counter, '&nbsp;');
            };

            var incr_project_event_counter = function(project) {
                var new_value;
                var counter = get_project_event_counter(project);
                var current_value = get_project_event_counter_value(counter);
                highlight_counter(counter, true);
                if (Boolean(current_value)) {
                    new_value = current_value + 1;
                } else {
                    new_value = 1;
                }
                set_project_event_counter_value(counter, new_value);
            };

            var handle_event_message = function(data) {
                var namespace = data['namespace'];
                var event_id = data['uid'];
                var channel = data['channel'];
                var event_data = data['data'];
                var project_id = data['project_id'];
                project = get_project_by_id(project_id);
                var active_tab_id = get_active_tab_id();
                var tab = get_tab_for_project(project);

                if (tab.length > 0) {
                    // tab already opened and meta already loaded
                    var container = get_content_for_project(project).find('.log');
                    render_event(container, project, namespace, event_id, channel, event_data);
                } else {
                    if (active_tab_id !== options.project_tab) {
                        highlight_tab(global_projects[options.project_tab], true);
                    }
                }
                if (active_tab_id !== project_id) {
                    incr_project_event_counter(project);
                    highlight_tab(project, true);
                }
            };

            var connect = function() {
                disconnect();

                //noinspection JSUnresolvedFunction
                connection = new SockJS(window.location.protocol + '//' + window.location.host + options.socket_url, null, {
                    protocols_whitelist: options.transports
                });

                connection.onopen = function() {
                    //console.log('Connected.');
                    $('.not-connected').hide();
                    $('.connected').show();
                    $('.pill').removeClass('pill-danger');
                };

                connection.onmessage = function(e) {
                    var body = $.parseJSON(e.data);
                    handle_event_message(body);
                };

                connection.onclose = function() {
                    //console.log('Disconnected.');
                    connection = null;
                    window.setTimeout(function(){
                        $('.connected').hide();
                        $('.not-connected').show();
                        $('.pill').addClass('pill-danger');
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

            var prepare_project = function(project) {
                if (project['owner'] == get_current_user_id()) {
                    project['is_owner'] = true;
                }
                return project;
            };

            var render_project = function(project, container) {
                var prepared_project = prepare_project(project);
                var html = project_template.render(prepared_project);
                container.append(html);
            };

            var render_project_list = function() {
                var container = get_content_for_project(global_projects[options.project_tab]);
                clear_element_content(container);
                for (index in options.projects) {
                    //noinspection JSUnfilteredForInLoop
                    var project = options.projects[index];
                    render_project(project, container);
                }
            };

            var show_event = function(event_id, fade) {
                var event_element = $('#event-' + event_id);
                if (fade === true) {
                    event_element.fadeIn();
                } else {
                    event_element.show();
                }
            };

            var render_event = function(container, project, namespace, event_id, channel, event_data) {

                var html = event_template.render({
                    'event_id': event_id,
                    'channel': channel,
                    'data': prettify(event_data),
                    'namespace': namespace,
                    'project': project
                });

                var prepared_html = prepare_html(html);

                container.prepend(prepared_html);

                var fade = true;

                show_event(event_id, fade);

                container.find('.event:gt(' + options.max_events_amount + ')').remove();
            };

            var create_tab = function(project) {
                project['tab_text'] = make_tab_text(project['name']).toLowerCase();
                var tab_content = tab_pane_template.render(project);
                var tab_element = tab_template.render(project);
                $('#tab-content').append(tab_content);
                global_tabs.append(tab_element);
            };

            var open_tab = function(project) {
                clear_project_event_counter(project);
                var current_tab = $('#tab-' + project['_id']);
                if (current_tab.length) {
                    current_tab.tab('show');
                }
            };

            global_content.on('click', '[data-tab-open]', function() {
                var project_id = $(this).attr('data-tab-open');
                if (!(project_id in global_projects)) {
                    global_tabs.find('a:first').tab('show');
                    return false;
                }
                var project = global_projects[project_id];
                open_tab(project);
                highlight_tab(project, false);
                return false;
            });

            global_content.on('click', '.namespace', function() {
                var self = $(this);
                var list_element = self.parents('li:first');
                if (list_element.hasClass('active')) {
                    list_element.removeClass('active');
                } else {
                    list_element.addClass('active');
                }
            });

			var route = function(tab) {
				var project_id = tab.attr('data-id');
                var project = get_project_by_id(project_id);
                highlight_tab(project, false);
                clear_project_event_counter(project);
                switch (project_id) {
                    case options.project_tab:
                        break;
                    default:
                        $.noop();
                }
			};

            var initialize = function() {

                create_socket_connection();

                render_project_list();

                if (options.projects) {
                    for (var index in options.projects) {
                        //noinspection JSUnfilteredForInLoop
                        var project = options.projects[index];
                        create_tab(project);
                    }
                }

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

            };

            initialize();
        }
    })
})(jQuery);