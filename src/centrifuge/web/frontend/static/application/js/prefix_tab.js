;(function($) {
    $.fn.extend({
        prefix_tab : function(custom_options) {

            var defaults,
                options,
                show_tab,
                hash_changed,
                initialize;

            defaults = {
                sep: '/',
                prefix: "tab_",
                default_route: null
            };

            options = $.extend(defaults, custom_options);

            show_tab = function(tabs) {
                var hash = document.location.hash;
                if (hash) {
                    tabs.find('a[href='+hash.replace(options.sep + options.prefix,"")+']').tab('show');
                } else {
                    if (options.default_route) {
                        window.location.hash = options.sep + options.prefix + options.default_route;
                    }
                }
            };

            initialize = function(tabs) {
                show_tab(tabs);

                tabs.on('shown', 'a', function (e) {
                    window.location.hash = e.target.hash.replace("#", "#" + options.sep + options.prefix);
                });

                if ("onhashchange" in window) {
                    hash_changed = function() {
                        show_tab(tabs);
                    };
                    window.onhashchange = hash_changed;
                }
            };

            return $(this).each(function(){
                var tabs = $(this);
                initialize(tabs);
            });
        }
    })
})(jQuery);