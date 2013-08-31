$(function(){

    var jsrender_vars = {};

	$.views.tags({
	    foreach: function(list) {
            /*
             * tag for jsrender which allows
             * to iterate over key-value in objects
             */
	        var ret = "";
	        var self= this;
	        $.each(list, function(idx, val) {
	        	var data = {
	        		'key': idx,
	        		'value': val,
                    'data': list
	        	};
	            ret += self.renderContent(data);
	        });
	        return ret;
	    },
        setvar: function(key, value) {
            jsrender_vars[key] = value;
        }
	});

    $.views.helpers({
        getvar: function(key) {
            return jsrender_vars[key];
        },
        lower: function(value) {
            return value.toLowerCase();
        },
        upper: function(value) {
            return value.toUpperCase();
        }
    });

    $('.content').on('click', 'a.source, a.namespace', function(){
		return false;
	});

});
