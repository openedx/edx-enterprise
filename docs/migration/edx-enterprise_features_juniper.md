# Edx Enterprise features documentation for juniper

## Make site-aware redirects.

Add Site Configuration support for Enterprise enrollments, allowing the user to be redirected to the correct site. To ensure seamless multi-tenancy support, configuring the LMS_ROOT_URL per site becomes essential. In the enterprise scenario, when enrolling for a course, it is crucial to access the correct LMS site by invoking this setting from the site configurations. However, this requirement will undergo a transformation once we adopt eox-tenant.

## Make site-aware redirects for the purchase workflow.

Adds the capability to make a site-aware redirect when the course purchase workflow is initiated. This is required to redirect the user to the appropriate ecommerce site. After implementing the aforementioned custom feature that facilitates redirection to the desired LMS site, it follows that upon selecting a verified seat, you will be redirected to the ecommerce site for course purchase.

### Test Enterprise:

- Clone and install our repository for Enterprise https://github.com/Pearson-Advance/edx-enterprise
- Ecommerce and Discovery partners must match.
- LMS site should be configured as follows: `{"COURSE_CATALOG_API_URL":"http://<discovery-url>:18381/api/v1/" "ECOMMERCE_API_URL":"http://<ecommerce-url>:18130", "SESSION_COOKIE_DOMAIN":"<principal-domain>" "LMS_ROOT_URL":"<lms-url>:18000", "ECOMMERCE_PUBLIC_URL_ROOT":"http://<ecommerce-url>:18130"}`
- Synchronize course metadata in Discovery https://edx-discovery.readthedocs.io/en/latest/introduction.html#data-loading.
- Go to an Enterprise enrollment URL, e.g.` <LMS-HOST>/enterprise/<enterprise-customer-id>/course/<course-id>/enroll/`
- Select a verified seat if you want to buy the course, you should be redirected to the desired ecommerce site.
- You should be redirected with the correct LMS_ROOT_URL.
