describe("Course enrollment page", function () {
    beforeEach(function () {
        jasmine.getFixtures().fixturesPath = "__spec__/fixtures";
        loadFixtures("course_enrollment.html");
        setUpCourseDetailsModal();
    });
    describe("course details modal", function() {
        it("is not shown when the page is loaded", function () {
            expect($("#course-details-modal")).toBeHidden();
        });
        it("is shown when the view course details link is clicked", function () {
            $("#view-course-details-link").click();
            expect($("#course-details-modal")).not.toBeHidden();
        });
        it("exits when close button is clicked", function () {
            $("#course-details-modal").show();
            $("#modal-close-button").click();
            expect($("#course-details-modal")).toBeHidden();
        });
    });
});
