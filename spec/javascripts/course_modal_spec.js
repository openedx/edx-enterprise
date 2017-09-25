describe("Course modal template tag", function () {
    beforeEach(function () {
        jasmine.getFixtures().fixturesPath = "__spec__/fixtures";
        loadFixtures("course_enrollment.html");
        setUpCourseDetailsModal();
    });
    describe("course details modal", function() {
        it("is not shown when the page is loaded", function () {
            expect($("#course-details-modal-0")).toBeHidden();
        });
        it("is shown when the view course details link is clicked", function () {
            $("#view-course-details-link-0").click();
            expect($("#course-details-modal-0")).not.toBeHidden();
        });
        it("exits when close button is clicked", function () {
            $("#course-details-modal-0").show();
            $("#modal-close-button-0").click();
            expect($("#course-details-modal-0")).toBeHidden();
        });
    });
});
