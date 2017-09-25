/**
 * Perform a jQuery slide toggle on any elements that come after the `afterIndex`.
 * @param $element The element on whose children to perform the slide toggles on.
 * @param afterIndex The index of the child after which all children will be slide toggled.
 */
function slideToggleElementsAfter($element, afterIndex) {
    $element.children().each(function(index) {
        if (index > afterIndex) {
            $(this).slideToggle();
        }
    });
}

/**
 * Switch an existing class of an element with another.
 * @param $element The element whose class to switch.
 * @param currentClass The class to switch out.
 * @param newClass The class to switch in.
 */
function switchClass($element, currentClass, newClass) {
    $element.removeClass(currentClass);
    $element.addClass(newClass);
}

function toggleLinkText($element) {
    var seeMoreText = $('#see-more-text').text(),
        seeLessText = $('#see-less-text').text(),
        $faIcon = $element.prev('.fa'),
        $expandable = $element.closest('.expand-list-link-container').prev('.expandable');
    if ($element.text() === seeMoreText) {
        $element.text(seeLessText);
        switchClass($faIcon, 'fa-plus-circle', 'fa-minus-circle');
        $element.parent().attr('aria-expanded', 'true');
        $expandable.focus();
    } else {
        $element.text(seeMoreText);
        switchClass($faIcon, 'fa-minus-circle', 'fa-plus-circle');
        $element.parent().attr('aria-expanded', 'false');
        $element.parent().focus();
    }
}

function toggleContent($element) {
    var showAmount = $element.data('alwaysshow') - 1;
    slideToggleElementsAfter($element, showAmount);
}

(function() {
    "use strict";
    $(document).ready(function() {
        var $root = $('html, body');

        $('.expand-list-link').each(function(index) {
            var $expandable = $(this).parent().prev('.expandable'),
                $linkText = $(this).find('.text-underline');

            $(this).click(function(event) {
                event.preventDefault();
                toggleContent($expandable);
                toggleLinkText($linkText);
            });
        });

        $('a').not("[href='#!']").click(function() {
            $root.animate({
                scrollTop: $(this.hash).offset().top
            }, 500);
            return false;
        });
    });
}).call(this);
