function disableMode(reason) {
    var $course_mode = $("#id_course_mode");
    $course_mode.empty();
    $course_mode.append(makeOption(reason, ''));
    $course_mode.prop("disabled", true);
}

function makeOption(name, value) {
    return $("<option></option>").text(name).val(value);
}

function fillModeDropdown(data) {
    /*
     Given a set of data fetched from the enrollment API, populate the Course Mode
     dropdown with those options that are valid for the course entered in the
     Course ID text box.
     */
    var $course_mode = $("#id_course_mode");
    var previous_value = $course_mode.val();
    applyModes(data.course_modes);
    $course_mode.val(previous_value);
}

function applyModes(modes) {
    var $course_mode = $("#id_course_mode");
    $course_mode.empty();
    modes.forEach(function(el) {
        $course_mode.append(makeOption(el.name, el.slug));
    });
    $course_mode.prop("disabled", false);
}

function loadCourseModes(success, failure) {
    /*
     Make an API call to the enrollment API to get details about the course
     whose ID is currently in the Course ID text box.
     */
    var disableReason = gettext('Enter a valid course ID');
    $("#id_course").each(function (index, entry) {
        var courseId = entry.value;
        if (courseId === '') {
            disableMode(disableReason);
            return;
        }
        $.ajax({method: 'get', url: enrollmentApiRoot + "course/" + courseId})
            .done(success || fillModeDropdown)
            .fail(failure || function (err, jxHR, errstat) { disableMode(disableReason); });
    });
}

function switchTo(newEnrollmentMode, otherEnrollmentMode) {
    var newVal = newEnrollmentMode.$control.val();
    if (newVal == newEnrollmentMode.oldValue)
        return;
    if (newVal) {
        otherEnrollmentMode.$control.val("").prop("disabled", true);
    } else {
        otherEnrollmentMode.$control.val(otherEnrollmentMode.oldValue).prop("disabled", false);
    }
    newEnrollmentMode.oldValue = newVal;
    if (newEnrollmentMode.timeout) {
        clearTimeout(newEnrollmentMode.timeout);
    }
    newEnrollmentMode.timeout = setTimeout(newEnrollmentMode.apply, 300);
}

function addCheckedLearnersToEnrollBox() {
    var checkedEmailContainers = $(".enroll-checkbox:checked").parent().siblings('.email-container');
    var checked_emails = [];
    $.each(checkedEmailContainers, function () {
        checked_emails.push($.trim($(this).text()));
    });
    if ($("#id_email_or_username").val() === "") {
        $("#id_email_or_username").val(checked_emails.join(", "));
    }
}

function loadPage() {
    $("table.learners-table .delete-cell input[type='button']").click(function () {
        var $row = $(this).parents("tr");
        var email = $row.data("email");
        var message = interpolate(gettext("Are you sure you want to unlink %(email)s?"), {"email": email}, true);
        if (confirm(message)) {
            $.ajax({
                url: "?unlink_email=" + encodeURIComponent(email),
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

    var courseEnrollment = {
        $control: $("#id_course"),
        oldValue: null,
        timeout: null,
        apply: loadCourseModes
    };

    var programEnrollment = {
        $control: $("#id_program"),
        oldValue: null,
        timeout: null,
        // TODO: pull data from edx-enterprise endpoint (to be created) or course catalog API
        apply: function() { applyModes(defaultModes); }
    };
    
    var defaultModes = [
        {slug: "", name: gettext("---------")},
        {slug: "audit", name: gettext("Audit")},
        {slug: "verified", name: gettext("Verified")},
        {slug: "professional", name: gettext("Professional Education")},
        {slug: "no-id-professional", name: gettext("Professional Education (no ID)")},
        {slug: "credit", name: gettext("Credit")},
        {slug: "honor", name: gettext("Honor")}
    ];

    courseEnrollment.$control.on("input blur paste", function (evt) {
        console.log("Handling "+evt.type+" on course ID input");
        switchTo(courseEnrollment, programEnrollment);
    });
    
    programEnrollment.$control.on("input blur paste", function(evt) {
        console.log("Handling "+evt.type+" on program ID input");
        switchTo(programEnrollment, courseEnrollment);
    });
    courseEnrollment.$control.parents("form").on("submit", function() {
       courseEnrollment.$control.oldValue = null;
       programEnrollment.$control.oldValue = null;
    });

    if (courseEnrollment.$control.val()) {
        courseEnrollment.$control.trigger("input");
    } else if (programEnrollment.$control.val()) {
        programEnrollment.$control.trigger("input");
    }
    $("#learner-management-form").submit(addCheckedLearnersToEnrollBox);
}

$(loadPage());
