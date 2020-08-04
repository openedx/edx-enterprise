# Postman collection for Canvas work

Just to help local dev and testing with Canvas

First ensure you have canvas setup as per
https://openedx.atlassian.net/wiki/spaces/SOL/pages/1644462995/Work+with+a+local+Canvas+Learning+Management+System+on+Mac+OSX

Import this collection into postman


## To use this collection

Setup a postman environment and setup these vars

* canvas_url: usually just http://localhost:3000
* client_id : for oauth requests only
* client_secret: for oauth requests only
* access_token: once you have it (it will be plugged into requests as a bearer token). only used for post/put requests like create course
* code: the code returned by the oauth2 endpoints used to fetch access tokens (only applicable to
the `login/oauth2/token` endpoint)

Most endpoints are wired up to use these vars, but if not, fix them!
