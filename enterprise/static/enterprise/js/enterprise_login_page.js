function redirectToURL(redirectURL) {
    location.href = redirectURL;
}

function setupFormSubmit() {
    $('#enterprise-login-form').submit(function(event){
        event.preventDefault();
        var enterpriseSlug = $("#id_enterprise_slug").val();

        $("#activate-progress-icon").removeClass("is-hidden");
        $("#enterprise-login-submit").attr("disabled", true);

        $.ajax({
            url : "/enterprise/login",
            method : "POST",

            beforeSend: function (xhr) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie("csrftoken"));
            },

            data : {
                enterprise_slug : enterpriseSlug
            },

            success: function(data) {
                redirectToURL(data.url);
            },

            error : function(xhr) {
                $("#activate-progress-icon").addClass("is-hidden");
                $("#enterprise-login-submit").attr("disabled", false);
                $("#enterprise-login-form-error")
                .text(xhr.responseJSON.errors.join(", "))
                .removeClass( "is-hidden" );
            }
        });
    });
}

(function() {
    "use strict";

    $(document).ready(function() {
        setupFormSubmit();
    });
}).call(this);
