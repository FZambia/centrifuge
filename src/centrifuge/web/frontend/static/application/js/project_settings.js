;(function($) {
    $.extend({
        centrifuge_project_settings : function(custom_options) {

            var defaults,
                options,
                initialize;

            defaults = {
                tab_prefix: "/tab_",
                default_route: '#/tab__projects',
                current_user: {}
            };

            options = $.extend(defaults, custom_options);

            initialize();
        }
    })
})(jQuery);