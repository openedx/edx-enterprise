var enrollmentApiRoot = 'http://localhost/'
var gettext = function (arg) {
    return arg;
}

describe("Course mode dropdown", function () {
    
    beforeEach(function () {
        jasmine.getFixtures().fixturesPath = '__spec__/fixtures';
        loadFixtures('course_mode_dom_mock.html');
        loadPage();
        jasmine.Ajax.install();
    });

    afterEach(function () {
        jasmine.Ajax.uninstall();
    });

    describe("on page load", function () {
        it("indicates that a valid course ID is required on page load.", function () {
            expect($("#id_course_mode")).toContainText("Enter a valid course ID");
        });

        it("has a single item in the mode dropdown on page load.", function () {
            expect($("#id_course_mode")).toHaveLength(1);
        });

        it("has a disabled mode dropdown on page load.", function () {
            expect($("#id_course_mode")).toBeDisabled();
        });
    });

    describe("when filling the mode dropdown with data", function () {
        beforeEach(function (done) {
            result = fillModeDropdown({
                course_modes: [
                    {
                        name: 'Jedi Knight 101',
                        slug: 'honor'
                    },
                    {
                        name: 'Death and Taxes',
                        slug: 'audit'
                    }
                ]
            });
            done();
        }, 5000)

        it("renders correctly", function () {
            dropdown = $("#id_course_mode");
            expect(dropdown).not.toBeDisabled();
            expect(dropdown).toContainElement("option[value='honor']");
            expect(dropdown).toContainElement("option[value='audit']");
            expect(dropdown).toHaveText("Jedi Knight 101Death and Taxes");
        });
    });

    it("makes the correct API call for course mode", function () {
        $("#id_course").val("course1");
        loadCourseModes();
        var request = jasmine.Ajax.requests.mostRecent();
        expect(request.url).toBe('http://localhost/course/course1');
        expect(request.method).toBe('GET');
    });
});
