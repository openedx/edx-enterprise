function focusableElementsSelector() {
    return [
        'a[href], area[href], input:not([disabled]), select:not([disabled]),',
        'textarea:not([disabled]), button:not([disabled]), iframe, object, embed,',
        '*[contenteditable]'
    ].join(' ');
}

function setTabIndexing(containerSelector, ariaHidden, tabIndex) {
    var container = $(containerSelector),
        focusableItems = container.find('*').filter(focusableElementsSelector()).filter(':visible');
    container.attr('aria-hidden', ariaHidden);
    focusableItems.attr('tabindex', tabIndex);
}

function toggleModal(modalSelector, index, visible) {
    var ariaHidden = 'true',
        tabIndex = '0',
        focusSelector = '#view-course-details-link-' + index;

    if (visible) {
        ariaHidden = 'false';
        tabIndex = '-1';
        focusSelector = '#modal-close-button-' + index;
    }

    $(modalSelector).toggle(visible);
    $('body').toggleClass('open-modal', visible);

    $(modalSelector).attr('aria-hidden', ariaHidden);
    $(focusSelector).focus();
    setTabIndexing('.enterprise-container, .logo-container', ariaHidden, tabIndex);
}

function showModal(modalSelector, index) {
    toggleModal(modalSelector, index, true);
}

function hideModal(modalSelector, index) {
    toggleModal(modalSelector, index, false);
}

function setUpCourseDetailsModal() {
    $("a.view-course-details-link").each(function(index) {
        var modalSelector = "#course-details-modal-" + index;

        // Show the modal when clicking on the link.
        $(this).click(function(event) {
            event.preventDefault();
            showModal(modalSelector, index);
        });

        // Hide the modal when clicking the close button or elsewhere on the screen.
        $(modalSelector).click(function(event) {
            var target = $(event.target);
            if (target.hasClass('modal') || target.hasClass('modal-close-button')) {
                event.preventDefault();
                hideModal(modalSelector, index);
            }
        });

        // Hide the modal when ESC is pressed and the modal is focused
        $(document).keydown(function(event) {
            if ($(modalSelector).is(':visible') && event.keyCode === 27) {
                event.preventDefault();
                hideModal(modalSelector, index);
            }
        });
    });
}

(function() {
    "use strict";
    $(document).ready(function() {
        setUpCourseDetailsModal();
    });
}).call(this);
