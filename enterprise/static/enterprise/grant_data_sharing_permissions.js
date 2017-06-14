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

function hideBackgroundFromTabIndex() {
    $(".background-input").attr("tabindex", "-1");
    $(".consent-container").attr("aria-hidden", "true");
}

function showBackgroundInTabIndex() {
    $(".background-input").attr("tabindex", "0");
    $(".consent-container").attr("aria-hidden", "false");
}

function hideConsentConfirmationModal() {
    $("body").removeClass("open-modal");
    $("#consent-confirmation-modal").hide();
    showBackgroundInTabIndex();
}

function loadConsentPage() {
    $("#failure-link").click(function (event) {
        $("body").addClass("open-modal");
        $("#consent-confirmation-modal").show();
        $("#modal-close-button").focus();
        hideBackgroundFromTabIndex();
    });
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
    $("#review-policy-link").click(function (event) {
        event.stopPropagation();
        hideConsentConfirmationModal();
        togglePolicy(true);
        $("#consent-policy-dropdown-bar").focus();
    });
    $("#consent-confirmation-modal").click(function (event) {
        hideConsentConfirmationModal();
        $("#failure-link").focus();
    });
    $("#data-consent-checkbox").change(function (event) {
        $("#consent-button").attr("disabled", !(this.checked));
    });
    $(document).keydown(function (event) {
        if ((event.keyCode === 27) && ($("#consent-confirmation-modal").is(":visible"))) {
            // If the modal is shown, and the ESC key is pressed, hide the modal.
            hideConsentConfirmationModal();
            $("#failure-link").focus();
            event.preventDefault();
        }
    });
    $("#review-policy-link").keydown(function (event) {
        if (event.keyCode == 9 && !event.shiftKey){
            // Catch the tab keydown event when leaving the last control in the modal,
            // and move the focus to the first control in the modal.
            event.preventDefault();
            $("#modal-close-button").focus();
        }
    });
    $("#modal-close-button").keydown(function (event) {
        if (event.keyCode == 9 && event.shiftKey){
            // Catch the tab keydown with shift event when leaving the first control in
            // the modal, and move the focus to the last control in the modal.
            event.preventDefault();
            $("#review-policy-link").focus();
        }
    });
    var formDetails = {
        enrollmentDeferred: enrollmentDeferred,
        successUrl: successUrl,
        failureUrl: failureUrl,
        courseId: courseId,
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
