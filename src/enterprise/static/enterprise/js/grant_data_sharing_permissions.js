function togglePolicy (force_open) {
    var policy = $(".consent-policy").first();
    var icon = $("#consent-policy-dropdown-icon");
    if ((!policy.is(":visible")) || force_open) {
        policy.show();
        icon.removeClass("fa-chevron-right").addClass("fa-chevron-down");
        location.href = "#";
        location.href = "#consent-policy-dropdown-bar";
        $("#consent-policy-dropdown-bar").attr("aria-expanded", "true");
    } else {
        policy.hide();
        icon.removeClass("fa-chevron-down").addClass("fa-chevron-right");
        $("#consent-policy-dropdown-bar").attr("aria-expanded", "false");
  }
}

function loadConsentPage() {
    var $reviewPolicyLink = $('#review-policy-link');
    $("#consent-policy-dropdown-bar").click(function (event) {
        togglePolicy();
    });
    $(".policy-dropdown-link").click(function (event) {
        togglePolicy(true);
    });
    $("#modal-no-consent-button").click(function (event) {
        $("#data-consent-checkbox").attr("checked", false);
        $("#data-sharing").submit();
    });
    $reviewPolicyLink.click(function (event) {
        event.stopPropagation();
        togglePolicy(true);
        $("#consent-confirmation-modal").modal('hide');
        $("#consent-policy-dropdown-bar").focus();
    });
    $("#data-consent-checkbox").change(function (event) {
        $("#consent-button").attr("disabled", !(this.checked));
    });
    $reviewPolicyLink.keydown(function (event) {
        if (event.keyCode === 9 && !event.shiftKey){
            // Catch the tab keydown event when leaving the last control in the modal,
            // and move the focus to the first control in the modal.
            event.preventDefault();
            $("#modal-close-button").focus();
        }
    });
    $("#modal-close-button").keydown(function (event) {
        if (event.keyCode === 9 && event.shiftKey) {
            // Catch the tab keydown with shift event when leaving the first control in
            // the modal, and move the focus to the last control in the modal.
            event.preventDefault();
            $("#review-policy-link").focus();
        }
    });
    var formDetails = {
        deferCreation: deferCreation,
        successUrl: successUrl,
        failureUrl: failureUrl,
        courseId: courseId,
        programId: programId,
        licenseUuid: licenseUuid,
    };
    analytics.track("edx.bi.user.consent_form.shown", formDetails);
    analytics.trackForm($("#data-sharing"), function () {
        if ($("#data-consent-checkbox").is(":checked")) {
            return "edx.bi.user.consent_form.accepted";
        } else {
            return "edx.bi.user.consent_form.denied";
        }
    }, formDetails);
}
(function() {
    "use strict";

    $(document).ready(function() {
        loadConsentPage();
    });
}).call(this);
