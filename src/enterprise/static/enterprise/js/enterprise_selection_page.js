function redirectToURL(redirectURL) {
    location.href = redirectURL;
}

function setupFormSubmit() {
    $('#select-enterprise-form').submit(function(event){
        event.preventDefault();
        var selectedEnterpriseUUID = $("#id_enterprise").val();

        $("#activate-progress-icon").removeClass("is-hidden");
        $("#select-enterprise-submit").attr("disabled", true);

        $.ajax({
            url : "/enterprise/select/active",
            method : "POST",

            beforeSend: function (xhr) {
                xhr.setRequestHeader("X-CSRFToken", $.cookie("csrftoken"));
            },

            data : {
                enterprise : selectedEnterpriseUUID
            },

            success: function() {
                redirectToURL($("#id_success_url").val());
            },

            error : function(xhr) {
                $("#activate-progress-icon").addClass("is-hidden");
                $("#select-enterprise-submit").attr("disabled", false);
                $("#select-enterprise-form-error")
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