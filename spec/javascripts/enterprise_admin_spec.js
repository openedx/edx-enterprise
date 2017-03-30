var enrollmentApiRoot = 'http://localhost/';
var gettext = function (arg) {
    return arg;
};
var interpolate = function (arg) {
    return arg;
}
$.cookie = function (arg) {
    return null;
}

describe("Manage Learners form", function () {

    // yes, this is copied from defaultModes var in the manage_learners.js and no, it is not a problem
    // as tests should be self-explaining and tied implementation as little as possible.
    var defaultCourseModeOptions = [
        {slug: "", name: "---------"},
        {slug: "audit", name: "Audit"},
        {slug: "verified", name: "Verified"},
        {slug: "professional", name: "Professional Education"},
        {slug: "no-id-professional", name: "Professional Education (no ID)"},
        {slug: "credit", name: "Credit"},
        {slug: "honor", name: "Honor"}
    ];

    var courseModesFakeResponse = {
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
    };

    function expectOptionIn($select, optionValue, optionName) {
        var $option = optionValue
            ? $select.children("option[value="+optionValue+"]")
            : $select.children("option").filter(function() { return !$(this).val(); });

        expect($option).toExist();

        if (optionName) {
            expect($option).toHaveText(optionName);
        }
    }

    function expectOptionsAfterTimeout($select, options, timeout, doneCallback) {
        setTimeout(function () {
           for (var idx in options) {
               var option = options[idx];
               expectOptionIn($select, option.slug, option.name);
           }
           doneCallback();
        }, timeout);
    }
    
    beforeEach(function () {
        jasmine.getFixtures().fixturesPath = '__spec__/fixtures';
        loadFixtures('manage_learners_form.html');
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

        describe("after failed form submission", function() {
            it("should have course ID disabled if program ID is filled in", function() {
                $("#id_program").val("program1");
                loadPage();
                expect($("#id_course")).toBeDisabled();
            });

            it("should have program ID disabled if course ID is filled in", function() {
                $("#id_course").val("program1");
                loadPage();
                expect($("#id_program")).toBeDisabled();
            });

            it("loads course modes if course ID is filled", function(done) {
                $("#id_course").val("course1");
                loadPage();
                jasmine.Ajax
                    .stubRequest('http://localhost/course/course1')
                    .andReturn({
                        responseText: JSON.stringify(courseModesFakeResponse)
                    });

                setTimeout(function() {
                    expectOptionsAfterTimeout($("#id_course_mode"), courseModesFakeResponse.course_modes, 0, done);
                }, 600);
            });

            it("shows default course modes if program ID is filled", function(done) {
                $("#id_program").val("program1");
                loadPage();

                expectOptionsAfterTimeout($("#id_course_mode"), defaultCourseModeOptions, 600, done);
            });
        });
    });

    describe("when filling the course mode dropdown with data", function () {
        beforeEach(function (done) {
            fillModeDropdown(courseModesFakeResponse);
            done();
        }, 5000);

        it("renders correctly", function () {
            var dropdown = $("#id_course_mode");
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

    it("correctly escapes emails of users for removal", function () {
        spyOn(window, 'confirm').and.returnValue(true);
        $("#learner-unlink-button").click();
        var request = jasmine.Ajax.requests.mostRecent();
        expect(request.url).toBe('?unlink_email=escaped%2Bemail%40google.com');
    })

    describe("program ID and course ID inputs interaction", function() {
        function testInputs($sourceInput, $otherInput, eventType) {
            // precondition check
            expect($sourceInput).not.toBeDisabled();
            expect($otherInput).not.toBeDisabled();

            $sourceInput.val("Something");
            $sourceInput.trigger(eventType);
            expect($otherInput).toBeDisabled();
        }

        function reset($inputs){
            $inputs.val("").prop("disabled", false).trigger("input");
        }

        it("should disable course ID when putting data into program ID", function() {
            var $courseIdInput = $("#id_course");
            var $programIdInput = $("#id_program");
            var $inputs = $courseIdInput.add($programIdInput);

            reset($inputs);
            testInputs($programIdInput, $courseIdInput, "input");
            reset($inputs);
            testInputs($programIdInput, $courseIdInput, "blur");
            reset($inputs);
            testInputs($programIdInput, $courseIdInput, "paste");
        });

        it("should disable program ID when putting data into course ID", function() {
            var $courseIdInput = $("#id_course");
            var $programIdInput = $("#id_program");
            var $inputs = $courseIdInput.add($programIdInput);

            reset($inputs);
            testInputs($courseIdInput, $programIdInput, "input");
            reset($inputs);
            testInputs($courseIdInput, $programIdInput, "blur");
            reset($inputs);
            testInputs($courseIdInput, $programIdInput, "paste");
        });
    });

    describe("program ID", function() {
        it("should restore default course modes options when filled", function(done) {
            var $programIdInput = $("#id_program");
            var $courseModeSelect = $("#id_course_mode");

            // precondition check
            expect($courseModeSelect.children()).toHaveLength(1);

            $programIdInput.val("QWERTY").trigger("input");

            setTimeout(function() {
                for (var idx in defaultCourseModeOptions) {
                    var option = defaultCourseModeOptions[idx];
                    expectOptionIn($courseModeSelect, option.slug, option.name);
                }
                done();
            }, 600);
        });
    })
});

describe("Enroll checkboxes", function () {

    beforeEach(function () {
        jasmine.getFixtures().fixturesPath = '__spec__/fixtures';
        loadFixtures('manage_learners_form.html');
        loadPage();
    });

    describe("when submitting the form and there is no value in the email box", function () {
        beforeEach(function (done) {
            result = addCheckedLearnersToEnrollBox();
            done();
        }, 5000);

        it("fills in the email box with the emails of checked users", function () {
            expect($("#id_email_or_username").val()).toBe('peter@yarrow.com, mary@travers.com');
        });
    });

    describe("when submitting the form and there is a value in the email box", function () {
        beforeEach(function (done) {
            $("#id_email_or_username").val('john@smith.com')
            result = addCheckedLearnersToEnrollBox();
            done();
        }, 5000);

        it("keeps the value that was already in the box", function () {
            expect($("#id_email_or_username").val()).toBe("john@smith.com")
        });
    })
});
