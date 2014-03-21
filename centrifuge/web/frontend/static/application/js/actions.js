$(function(){
    var editor = ace.edit("data-editor");
    editor.setTheme("ace/theme/monokai");
    editor.setShowPrintMargin(false);
    editor.setFontSize(12);
    editor.getSession().setMode('ace/mode/json');
    editor.getSession().setUseSoftTabs(true);
    editor.getSession().setUseWrapMode(true);

    var result_template = $('#result_template');
    var form = $('form');
    var textarea = $('#data');
    var submit_button = form.find('[type="submit"]');
    var form_message = $('#form-message');
    var form_result = $('#form-result');

    function show_error(text) {
        form_message.stop().hide().removeClass('box-success').addClass('box-error').text(text).fadeIn();
    }

    function show_success(text) {
        form_message.stop().hide().removeClass('box-error').addClass('box-success').text(text).fadeIn();
    }

    function post_action(url, data) {
        $.post(url, data, function(data){
            var html = result_template.render({
                "data": prettify_json(data)
            });
            form_result.html(html);
            show_success("successfully sent");
            submit_button.attr('disabled', false);
        }, "json").error(function() {
            show_error("error occurred");
            submit_button.attr('disabled', false);
        });
    }

    form.on('submit', function(){
        if (textarea.is(':disabled') === false) {
            var val = editor.getSession().getValue();
            if (val) {
                try {
                    var json = JSON.stringify(JSON.parse(val));
                    textarea.val(json);
                } catch (e) {
                    show_error("malformed JSON");
                    return false;
                }
            } else {
                show_error("JSON data required");
                return false;
            }
        }
        var to_send = $(this).serialize();
        var url = $(this).attr('action');
        submit_button.attr('disabled', true);
        post_action(url, to_send);
        return false;
    });

    var fields = ["channel", "data", "user"];

    var method_fields = {
        "publish": ["channel", "data"],
        "presence": ["channel"],
        "history": ["channel"],
        "unsubscribe": ["channel", "user"],
        "disconnect": ["user"]
    };

    $('[name="method"]').on('change', function(){
        var method = $(this).val();
        var fields_to_show = method_fields[method];
        for (var i in fields_to_show) {
            var field = $('#' + fields_to_show[i]);
            field.attr('disabled', false).parents('.form-group:first').show();
        }
        for (var k in fields) {
            var field_name = fields[k];
            if (fields_to_show.indexOf(field_name) === -1) {
                $('#' + field_name).attr('disabled', true).parents('.form-group:first').hide();
            }
        }
    }).trigger('change');

});