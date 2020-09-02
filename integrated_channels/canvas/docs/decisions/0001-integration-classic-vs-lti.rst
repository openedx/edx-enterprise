Canvas Integration via Classic Integration model vs LTI
=======================================================

Status
------

Draft

Context
-------

We would like to capture points about the decision to choose the Class integration model
over LTI model, in order to make edX courses available in Canvas LMS for partner institutions.

Decision
--------

For Canvas integration, these following use cases are prioritized:

* Students can easily discover courses within their institution’s online learning experience
* Faculty can easily view student performance data within their institution’s online learning experience

There is another use case that is deemed not applicable w.r.t Canvas integration:

* Students can consume course content from within their institution's online learning experience

The classic integration model nicely supports the former use cases and allows students to take
courses on the edX platform once discovered in Canvas.

Furthermore, LTI does not support course discovery, which is essential to independent and
facilitated learning use-cases. hence we made a decision to choose the classic integration model.

Consequences
------------

Choosing classic over LTI does mean that the "Digital Notebook" use case will be harder/clunkier
to implement. LTI does very well as this. This factor may be re-considered in the future.
