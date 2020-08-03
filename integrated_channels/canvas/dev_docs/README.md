# Postman collection for Canvas work

Just to help local dev and testing with Canvas

First ensure you have canvas setup as per
https://openedx.atlassian.net/wiki/spaces/SOL/pages/1644462995/Work+with+a+local+Canvas+Learning+Management+System+on+Mac+OSX

Import this collection into postman


## To use this collection

Setup a postman environment and setup these vars

* canvas_url: usually just http://localhost:3000
* access_token: once you have it (it will be plugged into requests as a bearer token)

Most endpoints are wired up to use these vars, but if not, fix them!
