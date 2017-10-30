
// /////////////////////////////////////////////////////////////////////////////

$.fn.zato.data_table.PubSubTopic = new Class({
    toString: function() {
        var s = '<PubSubTopic id:{0} name:{1}>';
        return String.format(s, this.id ? this.id : '(none)',
                                this.name ? this.name : '(none)');
    }
});

// /////////////////////////////////////////////////////////////////////////////

$(document).ready(function() {
    $('#data-table').tablesorter();
    $.fn.zato.data_table.password_required = false;
    $.fn.zato.data_table.class_ = $.fn.zato.data_table.PubSubTopic;
    $.fn.zato.data_table.new_row_func = $.fn.zato.pubsub.topic.data_table.new_row;
    $.fn.zato.data_table.parse();
    $.fn.zato.data_table.before_submit_hook = $.fn.zato.pubsub.topic.before_submit_hook;
    $.fn.zato.data_table.setup_forms(['name', 'max_depth']);
})


$.fn.zato.pubsub.topic.create = function() {
    $.fn.zato.data_table._create_edit('create', 'Create a new pub/sub topic', null);
}

$.fn.zato.pubsub.topic.edit = function(id) {
    $.fn.zato.data_table._create_edit('edit', 'Update the pub/sub topic', id);
}

$.fn.zato.pubsub.topic.data_table.new_row = function(item, data, include_tr) {
    var row = '';

    if(include_tr) {
        row += String.format("<tr id='tr_{0}' class='updated'>", item.id);
    }

    var empty = '<span class="form_hint">---</span>';

    row += "<td class='numbering'>&nbsp;</td>";
    row += "<td class='impexp'><input type='checkbox' /></td>";

    var has_gd = data.has_gd ? "Yes" : "No";

    row += String.format('<td>{0}</td>', item.name);
    row += String.format('<td>{0}</td>', has_gd);
    row += String.format('<td>{0}</td>', item.max_depth);

    row += String.format('<td>{0}</td>', data.current_depth_link);

    row += String.format('<td>{0}</td>', empty);

    row += String.format('<td>{0}</td>', data.publishers_link);
    row += String.format('<td>{0}</td>', data.subscribers_link);

    row += String.format('<td>{0}</td>',
        String.format("<a href=\"javascript:$.fn.zato.pubsub.topic.clear('{0}')\">Clear</a>", data.id));

    row += String.format('<td>{0}</td>',
        String.format("<a href=\"javascript:$.fn.zato.pubsub.topic.edit('{0}')\">Edit</a>", data.id));

    row += String.format('<td>{0}</td>',
        String.format("<a href=\"javascript:$.fn.zato.pubsub.topic.delete_('{0}')\">Delete</a>", data.id));

    row += String.format("<td class='ignore item_id_{0}'>{0}</td>", data.id);
    row += String.format("<td class='ignore'>{0}</td>", data.is_internal);
    row += String.format("<td class='ignore'>{0}</td>", data.is_active);
    row += String.format("<td class='ignore'>{0}</td>", data.has_gd);

    if(include_tr) {
        row += '</tr>';
    }

    return row;
}

$.fn.zato.pubsub.topic.delete_ = function(id) {
    $.fn.zato.data_table.delete_(id, 'td.item_id_',
        'Pub/sub topic `{0}` deleted',
        'Are you sure you want to delete the pub/sub topic `{0}`?',
        true);
}

$.fn.zato.pubsub.topic.clear = function(id) {

    var instance = $.fn.zato.data_table.data[id];

    var http_callback = function(data, status) {
        var success = status == 'success';
        $('#current_depth_' + instance.id).html('0');
        $.fn.zato.user_message(success, data.responseText);
    }

    var jq_callback = function(ok) {
        if(ok) {
            var url = String.format('./clear/cluster/{0}/topic/{1}/', $(document).getUrlParam('cluster'), instance.id);
            $.fn.zato.post(url, http_callback, '', 'text');
        }
    }

    var q = String.format('Are you sure you want to clear topic `{0}`?', instance.name);
    jConfirm(q, 'Please confirm', jq_callback);
}

$.fn.zato.pubsub.topic.delete_message = function(topic_id, msg_id) {

    var instance = $.fn.zato.data_table.data[msg_id];

    var http_callback = function(data, status) {
        var success = status == 'success';
        if(success) {
            $.fn.zato.data_table.remove_row('td.item_id_', msg_id);
        }
        $.fn.zato.user_message(success, data.responseText);
    }

    var jq_callback = function(ok) {
        if(ok) {
            var url = String.format('/zato/pubsub/message/delete/cluster/{0}/msg/{1}',
                $(document).getUrlParam('cluster'), instance.id);
            $.fn.zato.post(url, http_callback, '', 'text');
        }
    }

    var q = String.format(
        'Are you sure you want to delete message `{0}`?<br/><center>Msg prefix {1}</center>', instance.id, instance.msg_prefix);
    jConfirm(q, 'Please confirm', jq_callback);
}
