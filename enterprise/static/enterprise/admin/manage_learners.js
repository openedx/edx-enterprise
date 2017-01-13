function disableMode() {
    $("#id_course_mode").each(function (index, dropdown) {
        dropdown.options.length = 0;
        dropdown.options[0] = new Option(gettext('Enter a valid course ID'), '');
        dropdown.disabled = true;
    });
}

function fillModeDropdown(data) {
    /*
    Given a set of data fetched from the enrollment API, populate the Course Mode
    dropdown with those options that are valid for the course entered in the
    Course ID text box.
    */ 
    $("#id_course_mode").each(function (index, dropdown) {
        previous_value = dropdown.value;
        dropdown.options.length = 0;
        data.course_modes.forEach(function (el) {
            dropdown.options[dropdown.options.length] = new Option(el.name, el.slug);
            dropdown.disabled = false;
            if(previous_value === el.slug) {
                /*
                If there was a valid value in the box _before_ we did our AJAX call,
                try setting the box to that previous value. Note that this might result
                in a different string value in the box; admins can set different names
                for the course modes available for a particular course.
                */
                dropdown.value = previous_value;
            }
        });
    });
}

function loadCourseModes(success, failure) {
    /*
    Make an API call to the enrollment API to get details about the course
    whose ID is currently in the Course ID text box.
    */
    $("#id_course").each(function (index, entry) {
        courseId = entry.value;
        if (courseId === '') {
            disableMode();
            return;
        }
        $.ajax({
            method: 'get',
            url: enrollmentApiRoot + "course/" + courseId,
            success: success || fillModeDropdown,
            error: failure || disableMode
        });
    });
}

function loadPage() {
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
            });
        }
    });
    $("#id_course").on('input', function (event) {
        /*
        We have to do two-step input/blur because some browsers (looking at you, Safari)
        don't properly send the .change() event when the input is filled with autocomplete.
        */
        event.target.dirty = true;
    });
    $("#id_course").blur(function (event) {
        /*
        Only call loadCourseModes if the Course ID text box is marked as "dirty"; this is
        to avoid making excessive numbers of redundant AJAX calls when it hasn't changed.
        */
        var target = event.target;
        if (target.dirty) {
            loadCourseModes();
            target.dirty = false;
        }
    });
    loadCourseModes();
}
$(loadPage());
