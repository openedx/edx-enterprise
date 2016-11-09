$(
    function () {
        $("table.learners-table .delete-cell input[type='button']").click(function () {
            var $row = $(this).parents("tr");
            var email = $row.data("email");
            var message = interpolate(gettext("Are you sure you want to unlink %(email)s?"), {"email": email}, true);
            if (confirm(message)) {
                $.ajax({
                    url: "?unlink_email=" + email,
                    method: "delete",
                    beforeSend: function (xhr) {
                        xhr.setRequestHeader("X-CSRFToken", $.cookie("csrftoken"));
                    }
                }).success(function () {
                    $row.remove();
                }).error(function (xhr, errmsg, err) {
                    alert(xhr.responseText);
                })
            }
        });
    }
);
