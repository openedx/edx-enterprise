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
                'Have an account through your company, school, or organization?' +
                'Enter your organization’s name below to sign in.'
            );
            expect($('#id_enterprise_slug').isPresent().toBeTruthy());
            expect($('#enterprise-login-submit').text().trim()).toBe('Login');
        });
    });
});
