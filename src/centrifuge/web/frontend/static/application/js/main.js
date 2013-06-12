;(function($) {
    $.extend({
        centrifuge_main : function(custom_options) {

            var defaults = {
                tab_prefix: "/tab_",
                max_tab_text_length: 10,
                max_events_amount: 100,
                current_user: {},
                project_tab: '_projects',
                projects: [],
                categories: {},
                socket_url: '/socket/',
                global_content_element: '#main-content',
                global_panel_element: '#panel',
                global_tabs_element: '#tabs'
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

            var global_panel = $(options.global_panel_element);

            var global_tabs = $(options.global_tabs_element);

            var global_filter = {};

            var global_offset = {};

			var global_projects = {};

            for (var index in options.projects) {
            	//noinspection JSUnfilteredForInLoop
                var project = options.projects[index];

                var project_id = project['_id'];

                global_offset[project_id] = 0;

                global_projects[project_id] = project;

                global_filter[project_id] = {
                    'category': [],
                    'channel': null
                }
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
            var project_list_panel_template = $('#project_list_panel_template');
            var project_panel_template = $('#project_panel_template');

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

            var get_panel_for_project = function(project) {
                var panel_selector = '#panel-'+ project['_id'];
                return $(panel_selector);
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
                var category = {
                    '_id': data['category_id'],
                    'name': data['category']
                };
                var event_id = data['event_id'];
                var channel = data['channel'];
                var event_data = data['data'];
                var project_id = data['project_id'];
                project = get_project_by_id(project_id);
                var active_tab_id = get_active_tab_id();
                var tab = get_tab_for_project(project);

                if (tab.length > 0) {
                    // tab already opened and meta already loaded
                    var container = get_content_for_project(project).find('.log');
                    render_event(container, project, category, event_id, channel, event_data);
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

                connection = new WebSocket('ws://' + window.location.host + options.socket_url);

                connection.onopen = function() {
                    console.log('Connected.');
                    $('.not-connected').hide();
                    $('.connected').show();
                    $('.pill').removeClass('pill-danger');
                };

                connection.onmessage = function(e) {
                    var body = $.parseJSON(e.data);
                    console.log(body);
                    handle_event_message(body);
                };

                connection.onclose = function() {
                    console.log('Disconnected.');
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

            var render_panel_for_project_list = function() {
                var projects_all = $('.project');


                var html = project_list_panel_template.render({});
                global_panel.append(html);

                $('#project-name-filter').on('keyup', function() {
                    var self = $(this);
                    var value = self.val();
                    if (value == '') {
                        projects_all.removeClass('project-name-filtered');
                    }

                    projects_all.each(function(){
                        var project = $(this);
                        var name = project.attr('data-project-name');
                        var display_name = project.attr('data-project-display');
                        if (name.toLowerCase().indexOf(value.toLowerCase()) > -1 || display_name.toLowerCase().indexOf(value.toLowerCase()) > -1 ) {
                            project.removeClass('project-name-filtered');
                        } else {
                            project.addClass('project-name-filtered');
                        }
                    });
                });
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

            var render_event = function(container, project, category, event_id, channel, event_data) {

                var html = event_template.render({
                    'event_id': event_id,
                    'channel': channel,
                    'data': event_data,
                    'category': category,
                    'project': project
                });

                var prepared_html = prepare_html(html);

                container.prepend(prepared_html);

                var fade = true;

                var project_filter = global_filter[project['_id']];

                if (project_filter['category'].length > 0 && project_filter['category'].indexOf(category['_id']) == -1) {
                    return;
                }

                if (project_filter['channel'] && event['channel'].toLowerCase().indexOf(project_filter['channel'].toLowerCase()) == -1) {
                    return;
                }

                show_event(event_id, fade);

                container.find('.event:gt(' + options.max_events_amount + ')').remove();
            };

            var render_panel_for_project = function(project) {
                var categories = options.categories[project['_id']];
                var data = {
                    'project': project,
                    'categories': categories
                };
                var html = project_panel_template.render(data);
                global_panel.append(html);
            };

            var create_tab = function(project) {
                project['tab_text'] = make_tab_text(project['name']);
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

            global_content.on('click', '.category', function() {
                var self = $(this);
                var list_element = self.parents('li:first');
                if (list_element.hasClass('active')) {
                    list_element.removeClass('active');
                } else {
                    list_element.addClass('active');
                }
            });

            global_content.on('click', '.apply-event-filter', function() {
                var project_id = get_active_tab_id();
                var project = get_project_by_id(project_id);
                global_offset[project_id] = 0;

                var panel = get_panel_for_project(project);

                var channel_val = panel.find('.channel-filter').val();
                var category_list_active = [];
                var category_list_all = [];
                panel.find('[data-category-id]').each(function() {
                    var self = $(this);
                    var category_id = self.attr('data-category-id');
                    category_list_all.push(category_id);
                    if (self.parents('li:first').hasClass('active')) {
                        category_list_active.push(category_id);
                    }
                });
                var category_list;
                if (category_list_active.length > 0) {
                    category_list = category_list_active;
                } else {
                    category_list = category_list_all;
                }
                global_filter[project_id] = {
                    'category': category_list,
                    'channel': channel_val
                };

                return false;
            });

            global_content.on('click', '.reset-event-filter', function() {
                var project_id = get_active_tab_id();
                var project = get_project_by_id(project_id);
                global_offset[project_id] = 0;
                var panel = get_panel_for_project(project);
                panel.find('[data-category-id]').each(function() {
                    $(this).parents('li:first').removeClass('active');
                });
                panel.find('.channel-filter').val('');
                panel.find('.apply-event-filter').trigger('click');
                return false;
            });

			var route = function(tab) {
				var project_id = tab.attr('data-id');
                var project = get_project_by_id(project_id);
                highlight_tab(project, false);
                clear_project_event_counter(project);
                $('.project-panel').hide();
                var project_list_panel = $('#project-list-panel');
                switch (project_id) {
                    case options.project_tab:
                        // display list of projects available for current user
                        project_list_panel.fadeIn();
                        break;
                    default:
                        // here we have an attempt to view project events
                        project_list_panel.hide();
                        $('#panel-' + project['_id']).fadeIn();
                }
			};

            var initialize = function() {

                create_socket_connection();

                render_project_list();
                render_panel_for_project_list();

                if (options.projects) {
                    for (var index in options.projects) {
                        var project = options.projects[index];
                        create_tab(project);
                        render_panel_for_project(project);
                    }
                }

                show_hashed_tab();

                // Change hash for page-reload
                global_tabs.on('shown', 'a', function (e) {
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