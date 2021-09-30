Adding course key - uuid mapping for Cornerstone
------------------------------------------------------

Status
======

Draft

Context
=======

At one point we were having transmitted courses to CSOD tenants fail with invalid chars contained within course metadata. 
To combat this, we decided to encode the course keys. This has resulted in some of the courses failing validation with a 
"course key too long" failures. There's a 50 char limit to course keys on the CSOD lms, so we need to limit the size of
our encoded course keys within the content metadata.

Simply truncating it would not allow for backwards compatibility or ensuring uniqueness. We also considered encoding
and then compress, but while this would most likely work for every course key (the largest length found in prod was 54 chars),
it can't properly guarantee the key to be under 50 chars, and we would have to worry with hashing the fact that 
it is one way. 

Decisions
=========

Using uuids as the course key as they are guaranteed to be 36 characters and don’t have to be url encoded. We will 
be creating a dictionary-like table to map the edx course key to a key that will be used as the course key in Cornerstone. 

Since we already have many courses in Cornerstone that the keys are under 50 characters, we will not be creating
new uuids in the dictionary, because that could lead to a course being duplicated on their system. The logic that is
currently implemented (using url encoded course key) will remain, unless the encoding is over 50 characters. 
The uuid will be generated when we are transmitting course content metadata, and also when they report learner 
data back to us. 


Consequences
============

As always, adding an additional table leads to more memory storage, and have a customized approach to Cornerstone
might lead to some confusion down the line. Code will be properly documented and lead back to this ADR to alleviate 
some of this. 
