describe("Program Enrollment Landing Page spec", function () {
    beforeEach(function () {
        jasmine.getFixtures().fixturesPath = "__spec__/fixtures";
        loadFixtures("program_enrollment.html");
    });
    describe("course details modal", function() {
        var $expandLink = $('#test-expand-link'),
            $seeMoreText = $('#see-more-text'),
            $seeLessText = $('#see-less-text'),
            $ul = $('#test-ul'),
            showIndex = $ul.data('alwaysshow') - 1;

        it("should show the #see-more-text text on the expand-list link " +
            "at page load", function () {
            expect($expandLink.text()).toEqual($seeMoreText.text());
        });
        it("should show the #see-less-text text on the expand-list-link " +
            "when clicked while text is #see-more-text", function () {
            $expandLink.click();
            expect($expandLink.text()).toEqual($seeLessText.text());
        });
        it("should show the #see-more-text text on the expand-list-link " +
            "when clicked while text is #see-less-text", function () {
            $expandLink.dblclick();
            expect($expandLink.text()).toEqual($seeMoreText.text());
        });
        it("should hide items in the expandable item past the data-alwaysshow index " +
            "at page load", function () {
            $ul.children().each(function(index) {
                if (index > showIndex) {
                    expect($(this)).toBeHidden();
                }
            });
        });
        it("should show items in the expandable item past the data-alwaysshow index " +
            "when the list is hidden and the expand-list link is clicked", function() {
            $expandLink.click();
            $ul.children().each(function(index) {
                if (index > showIndex) {
                    expect($(this)).toBeVisible();
                }
            });
        });
        it("should hide items in the expandable item past the data-alwaysshow index " +
            "when the list is showing and the expand-list link is clicked", function () {
            $expandLink.dblclick();
            $ul.children().each(function(index) {
                if (index > showIndex) {
                    expect($(this)).toBeHidden();
                }
            });
        });
    });
});
