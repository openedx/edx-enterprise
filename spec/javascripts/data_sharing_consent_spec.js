describe("Data sharing consent page", function () {
    beforeEach(function () {
        jasmine.getFixtures().fixturesPath = "__spec__/fixtures";
        loadFixtures("data_sharing_consent.html");
        loadConsentPage();
    });

    describe("main submission button", function () {
        it("is disabled on page load", function () {
            expect($("#consent-button")).toBeDisabled();
        });
        
        it("is enabled once the consent checkbox is checked", function() {
            $("#data-consent-checkbox").click();
            expect($("#consent-button")).not.toBeDisabled();
        });

        it("is disabled if the consent checkbox is checked then unchecked", function() {
            $("#data-consent-checkbox").click();
            expect($("#consent-button")).not.toBeDisabled();
            $("#data-consent-checkbox").click();
            expect($("#consent-button")).toBeDisabled();
        });
    });

    describe("modal confirmation div", function () {
        it("is not shown when the page is loaded", function () {
            expect($("#consent-confirmation-modal")).not.toHaveClass('show');
        });

        describe("review policy link", function () {
            beforeEach(function () {
                $("#consent-confirmation-modal").show();
            });

            it("is visible when the modal is open", function () {
                expect($("#review-policy-link")).not.toBeHidden();
            });
        });
    });

    describe("consent policy dropdown", function () {
        it("is not shown when the page is loaded", function () {
            expect($(".consent-policy")).toBeHidden();
        });

        it("is shown when the dropdown button is clicked", function () {
            $("#consent-policy-dropdown-bar").click();
            expect($(".consent-policy")).not.toBeHidden();
            console.log($("#consent-policy-dropdown-icon"));
            expect($("#consent-policy-dropdown-icon")).toHaveClass("fa-chevron-down");
        });

        it("is hidden when the dropdown button is clicked after it's been opened", function () {
            $("#consent-policy-dropdown-bar").click();
            expect($(".consent-policy")).not.toBeHidden();
            $("#consent-policy-dropdown-bar").click();
            expect($(".consent-policy")).toBeHidden();
            expect($("#consent-policy-dropdown-icon")).toHaveClass("fa-chevron-right");
        });
    });

    describe("analytics", function () {
        it("should fire a \"edx.bi.user.consent_form.shown\" event when loading the page", function () {
            expect(lastTrackedEvent).toBe('edx.bi.user.consent_form.shown');
        });

        it("should be set up to submit events when the form is submitted", function () {
            expect(lastTrackedForm.form.attr("id")).toBe("data-sharing");
        });

        describe("when the form is submitted", function () {
            it("should fire a \"edx.bi.user.consent_form.accepted\" event if the form checkbox is checked", function () {
                $("#data-consent-checkbox").click();
                expect(lastTrackedForm.callback()).toBe("edx.bi.user.consent_form.accepted");
            });

            it("should fire a \"edx.bi.user.consent_form.denied\" event if the form checkbox is not checked", function () {
                expect(lastTrackedForm.callback()).toBe("edx.bi.user.consent_form.denied");
            });
        });
    });
});
