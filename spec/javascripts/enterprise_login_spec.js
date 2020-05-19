describe('Enterprise Login Page', function () {
    beforeEach(function () {
        jasmine.getFixtures().fixturesPath = '__spec__/fixtures';
        loadFixtures('enterprise_login.html');
        setupFormSubmit();
    });

    describe('Rendering', function () {
        it('renders page correctly', function () {
            expect($('.enterprise-login-title').text()).toBe('Enter the organization name');
            expect($('.enterprise-login-message p').text()).toBe(
                'Have an account through your school, or organization?' +
                 'Enter your organization’s name below to sign in.'
            );
            expect($('#id_enterprise_slug').isPresent().toBeTruthy());
            expect($('#enterprise-login-submit').text().trim()).toBe('Login');
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
            .stubRequest('/enterprise/login')
            .andReturn({
                responseText: JSON.stringify({})
            });

            $( '#enterprise-login-submit' ).trigger( 'click' );

            var request = jasmine.Ajax.requests.mostRecent();
            expect(request.url).toBe('/enterprise/login');
            expect(request.method).toBe('POST');
            expect(request.data().enterprise_slug).toEqual(['dummy']);
            expect(redirectSpy.calls.count()).toEqual(1);
        });
    });
});
