function focusableElementsSelector() {
    return [
        'a[href], area[href], input:not([disabled]), select:not([disabled]),',
        'textarea:not([disabled]), button:not([disabled]), iframe, object, embed,',
        '*[tabindex], *[contenteditable]'
    ].join(' ');
}

function setTabIndexing(containerSelector, ariaHidden, tabIndex) {
    var container = $(containerSelector),
        focusableItems = container.find('*').filter(focusableElementsSelector()).filter(':visible');
    container.attr('aria-hidden', ariaHidden);
    focusableItems.attr('tabindex', tabIndex);
}

function toggleModal(modalSelector, visible) {
    var ariaHidden = 'true',
        tabIndex = '0',
        focusSelector = '#view-course-details-link';

    if (visible) {
        ariaHidden = 'false';
        tabIndex = '-1';
        focusSelector = '#modal-close-button';
    }

    $(modalSelector).toggle(visible);
    $('body').toggleClass('open-modal', visible);

    $(modalSelector).attr('aria-hidden', ariaHidden);
    $(focusSelector).focus();
    setTabIndexing('.enterprise-container', ariaHidden, tabIndex);
}

function showModal(modalSelector) {
    toggleModal(modalSelector, true);
}

function hideModal(modalSelector) {
    toggleModal(modalSelector, false);
}

function setUpCourseDetailsModal() {
    var modalSelector = "#course-details-modal";
    $("#view-course-details-link").click(function(event) {
        event.preventDefault();
        showModal(modalSelector);
    });
    $(modalSelector).click(function(event) {
        var target = $(event.target);
        if (target.hasClass('modal') || target.hasClass('modal-close-button')) {
            event.preventDefault();
            hideModal(modalSelector);
        }
    });
    // Hide the modal when ESC is pressed and the modal is focused
    $(document).keydown(function(event) {
        if ($(modalSelector).is(':visible') && event.keyCode === 27) {
            event.preventDefault();
            hideModal(modalSelector);
        }
    });
}

(function() {
    "use strict";
    $(document).ready(function() {
        setUpCourseDetailsModal();
    });
}).call(this);
