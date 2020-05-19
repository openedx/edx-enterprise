describe('Enterprise Selection Page', function () {
    beforeEach(function () {
        jasmine.getFixtures().fixturesPath = '__spec__/fixtures';
        loadFixtures('enterprise_select.html');
        setupFormSubmit();
    });

    describe('Rendering', function () {
        it('renders page correctly', function () {
            expect($('.select-enterprise-title').text()).toBe('Select an organization');
            expect($('.select-enterprise-message p').text()).toBe(
                'You have access to multiple organ' +
                'to sign up for courses. If you want to change organizations, sign out and sign back in.'
            );
            expect($('#select-enterprise-form label').text()).toBe('Organization:');

            var optionValues = $.map($('#id_enterprise option') ,function(option) {
                return option.value;
            });
            var optionTexts = $.map($('#id_enterprise option') ,function(option) {
                return option.text;
            });
            expect(optionValues).toEqual(
                ['6ae013d4-c5c4-474d-8da9-0e559b2448e2', '885f4d97-5a21-4e8a-8723-a434bc527e74']
            );
            expect(optionTexts).toEqual(['batman', 'riddler']);

            expect($('#select-enterprise-submit').text().trim()).toBe('Continue');
        });
    });

    describe('Form', function () {
        beforeEach(function () {
            jasmine.Ajax.install();
        });

        afterEach(function () {
            jasmine.Ajax.uninstall();
        });

        it('works expected on correct post data', function () {
            var redirectSpy = spyOn(window, 'redirectToURL');

            jasmine.Ajax
            .stubRequest('/enterprise/select/active')
            .andReturn({
                responseText: JSON.stringify({})
            });

            $( '#select-enterprise-submit' ).trigger( 'click' );

            var request = jasmine.Ajax.requests.mostRecent();
            expect(request.url).toBe('/enterprise/select/active');
            expect(request.method).toBe('POST');
            expect(request.data().enterprise).toEqual(['6ae013d4-c5c4-474d-8da9-0e559b2448e2']);
            expect(redirectSpy.calls.count()).toEqual(1);
            expect(redirectSpy.calls.first().args).toEqual(['/dashboard']);
        });

        it('works expected on incorrect post data', function () {
            var response = {
                'errors': ['Enterprise not found']
            };

            jasmine.Ajax
            .stubRequest('/enterprise/select/active')
            .andReturn({
                status: 400,
                responseText: JSON.stringify(response)
            });

            $( '#select-enterprise-submit' ).trigger( 'click' );

            var request = jasmine.Ajax.requests.mostRecent();
            expect(request.url).toBe('/enterprise/select/active');
            expect(request.method).toBe('POST');

            expect($('#select-enterprise-form-error').text().trim()).toEqual(response.errors[0]);
        });
    });
});
