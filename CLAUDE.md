# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Test Commands
- `make test` - Run all tests in current virtualenv
- `make diff_cover` - Run tests and report diff coverage
- `make test-all` - Run quality checks, all tests in every supported env (Python/Django versions) and Jasmine JS tests
- `py.test` - Basic pytest execution (after installing test requirements)
- `py.test --cov-report html` - Generate HTML coverage report
- `tox` - Run tests on all supported Python/Django combinations
- `tox -e quality` - Run quality checks (pylint, pycodestyle, isort)
- `tox -e jasmine` - Run Jasmine JavaScript tests
- `tox -e docs` - Build documentation and run quality checks

### Quality and Linting
- `make quality` or `tox -e quality` - Run all Python quality checks
- `make pylint` - Run pylint outside of tox
- `make pycodestyle` - Run pycodestyle outside of tox
- `make jshint` - Run JavaScript linting
- `make isort` - Format imports with isort

### Development Setup
- `make requirements` - Install development environment requirements
- `make requirements.js` - Install JavaScript requirements for local development
- `pip install -qr requirements/dev.txt --exists-action w` - Install dev dependencies directly

### Static Assets
- `make static` - Gather all static assets for production (with webpack optimization)
- `make static.dev` - Gather static assets for development
- `make static.watch` - Watch for static asset changes during development

### Documentation
- `make docs` - Generate Sphinx documentation and open in browser
- `tox -e docs` - Build docs with quality checks

### Database
- `./manage.py migrate` - Run Django migrations
- `python manage.py collectstatic --noinput` - Collect static files

## Architecture Overview

**edx-enterprise** is a pluggable Django application designed to run within edx-platform. It provides enterprise features to the Open edX platform, centered around the concept of Enterprise Customers (organizations that consume courses).

### Core Components

#### Main Applications
- `enterprise/` - Core enterprise functionality and models
- `consent/` - Data sharing consent management
- `integrated_channels/` - Third-party LMS integrations (Canvas, Blackboard, Cornerstone, Degreed, etc.)
- `enterprise_learner_portal/` - Learner portal API endpoints

#### Key Models (enterprise/models.py)
- `EnterpriseCustomer` - Represents an organization consuming courses
- `EnterpriseCustomerUser` - Links users to enterprise customers
- `EnterpriseCourseEnrollment` - Enterprise-specific course enrollments
- `EnterpriseCustomerCatalog` - Content catalogs for enterprise customers
- `EnterpriseCustomerReportingConfiguration` - Reporting and analytics setup

#### API Structure (enterprise/api/v1/)
The API is organized into views for different enterprise entities:
- `enterprise_customer.py` - Customer management
- `enterprise_course_enrollment.py` - Enrollment management
- `enterprise_customer_user.py` - User management
- `enterprise_group.py` - Group management
- `analytics_summary.py` - Analytics and reporting

#### Integrated Channels
Each channel (Canvas, Blackboard, Cornerstone, Degreed, etc.) follows a consistent pattern:
- **Exporters** - Transform edX data into channel-specific formats
- **Transmitters** - Send data to third-party systems via APIs
- **Models** - Store channel-specific configuration and transmission audit logs

### Development Patterns

#### Testing Requirements
- All new Python code must have 100% diff coverage
- High code quality standards enforced via pylint, pycodestyle, isort
- JavaScript tests use Jasmine framework
- Tests should use REST APIs rather than Python APIs when integrating with edx-platform

#### Separation from edx-platform
- Use REST APIs rather than Python APIs when possible for edx-platform integration
- Encapsulate Python API usage in modules/classes for future migration
- Extensive unit test coverage for all API clients

#### Database Migrations
The project has an extensive migration history (240+ migrations). When creating new migrations:
- Follow Django best practices
- Test migrations thoroughly in both directions
- Consider data migration needs for existing enterprise customers

## Common Development Workflows

### Adding New Integrated Channel
1. Create new directory in `integrated_channels/`
2. Implement concrete subclass of `IntegratedChannelApiClient`
3. Create channel-specific models extending `EnterpriseCustomerPluginConfiguration`
4. Implement exporters and transmitters following existing patterns
5. Add URL patterns and admin configuration

### Working with Enterprise Customer Data
- Use `EnterpriseCustomer.objects.get()` to retrieve customers
- Leverage `EnterpriseCustomerUser` for user-customer relationships
- Use enterprise catalog queries for content filtering
- Follow audit logging patterns for compliance

### API Development
- Extend appropriate base views in `enterprise/api/v1/views/`
- Use DRF serializers for data validation and transformation
- Implement proper permissions using enterprise RBAC
- Add comprehensive API documentation

## Technology Stack
- **Backend**: Django 4.2/5.2, Django REST Framework
- **Frontend**: Webpack, Sass, jQuery (legacy), Paragon components
- **Database**: PostgreSQL (with extensive migration history)
- **Testing**: pytest, tox, Jasmine
- **Quality**: pylint, pycodestyle, isort, jshint
- **Integrations**: REST APIs for third-party systems
- **Security**: Fernet field encryption, PGP support for sensitive data
- I'll always have to run the tests manually

## Before opening a PR or pushing a branch

Run a self-check on the diff before creating a PR or pushing:
1. Compute effective LoC — exclude lockfiles, generated files, snapshots, and vendor code.
2. Count effective touched files — exclude the above plus one-to-one test pairs.
3. If effective LoC > 400 or effective files > 10, stop and propose a split before proceeding.
4. Report the result inline before continuing.

## Key Principles

- Search the codebase before assuming something isn't implemented
- Write comprehensive tests with clear documentation
- Follow Test-Driven Development when refactoring or modifying existing functionality
- Always write tests for new functionality you implement
- Keep changes focused and minimal
- Follow existing code patterns
- Prefer the `ddt` package for parameterized tests to reduce code duplication

## Documentation & Institutional Memory

- Document new functionality in `docs/references/`
- When you learn something important about how this codebase works (gotchas, non-obvious
  patterns, integration quirks), capture it in the relevant `docs/references/` file or
  in `docs/architecture-patterns.md`
- These docs are institutional memory - future sessions (yours or others) will benefit
  from what you record here

## Testing Notes

- Uses pytest with Django integration
- Coverage reporting enabled by default
- PII annotation checks required for Django models
