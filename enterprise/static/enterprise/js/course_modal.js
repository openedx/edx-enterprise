function focusableElementsSelector() {
    return [
        'a[href], area[href], input:not([disabled]), select:not([disabled]),',
        'textarea:not([disabled]), button:not([disabled]), iframe, object, embed,',
        '*[contenteditable]'
    ].join(' ');
}

function lastFocusableElement($container) {
    return $container.find('*').filter(focusableElementsSelector()).last();
}

(function() {
    "use strict";

    $(document).ready(function() {
        $('.modal').each(function() {
            lastFocusableElement($(this)).keydown(function (event) {
                if (event.keyCode === 9 && !event.shiftKey) {
                    // Catch the tab keydown event when leaving the last control in the modal,
                    // and move the focus to the first control in the modal.
                    event.preventDefault();
                    $(this).closest('.modal').find('button.close').focus();
                }
            });
        });

        $(".close").keydown(function (event) {
            if (event.keyCode === 9 && event.shiftKey) {
                // Catch the tab keydown with shift event when leaving the first control in
                // the modal, and move the focus to the last control in the modal.
                event.preventDefault();
                lastFocusableElement($(this).closest('.modal')).focus();
            }
        });
    });
}).call(this);
