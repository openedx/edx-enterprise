function slideToggleElementsAfter($element, afterIndex) {
    $element.children().each(function(index) {
        if (index > afterIndex) {
            $(this).slideToggle();
        }
    });
}

function toggleLinkText($element) {
    var seeMoreText = $('#see-more-text').text(),
        seeLessText = $('#see-less-text').text();
    if ($element.text() === seeMoreText) {
        $element.text(seeLessText);
    } else {
        $element.text(seeMoreText);
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
