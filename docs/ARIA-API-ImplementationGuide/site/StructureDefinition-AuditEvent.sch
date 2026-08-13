<?xml version="1.0" encoding="UTF-8"?>
<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2">
  <sch:ns prefix="f" uri="http://hl7.org/fhir"/>
  <sch:ns prefix="h" uri="http://www.w3.org/1999/xhtml"/>
  <!-- 
    This file contains just the constraints for the profile AuditEvent
    It includes the base constraints for the resource as well.
    Because of the way that schematrons and containment work, 
    you may need to use this schematron fragment to build a, 
    single schematron that validates contained resources (if you have any) 
  -->
  <sch:pattern>
    <sch:title>f:AuditEvent</sch:title>
    <sch:rule context="f:AuditEvent">
      <sch:assert test="count(f:period) &lt;= 0">period: maximum cardinality of 'period' is 0</sch:assert>
      <sch:assert test="count(f:outcomeDesc) &lt;= 0">outcomeDesc: maximum cardinality of 'outcomeDesc' is 0</sch:assert>
      <sch:assert test="count(f:purposeOfEvent) &lt;= 0">purposeOfEvent: maximum cardinality of 'purposeOfEvent' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:AuditEvent/f:agent</sch:title>
    <sch:rule context="f:AuditEvent/f:agent">
      <sch:assert test="count(f:type) &lt;= 0">type: maximum cardinality of 'type' is 0</sch:assert>
      <sch:assert test="count(f:role) &lt;= 0">role: maximum cardinality of 'role' is 0</sch:assert>
      <sch:assert test="count(f:who) &lt;= 0">who: maximum cardinality of 'who' is 0</sch:assert>
      <sch:assert test="count(f:altId) &lt;= 0">altId: maximum cardinality of 'altId' is 0</sch:assert>
      <sch:assert test="count(f:location) &lt;= 0">location: maximum cardinality of 'location' is 0</sch:assert>
      <sch:assert test="count(f:policy) &lt;= 0">policy: maximum cardinality of 'policy' is 0</sch:assert>
      <sch:assert test="count(f:media) &lt;= 0">media: maximum cardinality of 'media' is 0</sch:assert>
      <sch:assert test="count(f:network) &lt;= 0">network: maximum cardinality of 'network' is 0</sch:assert>
      <sch:assert test="count(f:purposeOfUse) &lt;= 0">purposeOfUse: maximum cardinality of 'purposeOfUse' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:AuditEvent/f:agent/f:network</sch:title>
    <sch:rule context="f:AuditEvent/f:agent/f:network">
      <sch:assert test="count(f:address) &lt;= 0">address: maximum cardinality of 'address' is 0</sch:assert>
      <sch:assert test="count(f:type) &lt;= 0">type: maximum cardinality of 'type' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:AuditEvent/f:source</sch:title>
    <sch:rule context="f:AuditEvent/f:source">
      <sch:assert test="count(f:site) &lt;= 0">site: maximum cardinality of 'site' is 0</sch:assert>
      <sch:assert test="count(f:type) &lt;= 0">type: maximum cardinality of 'type' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:AuditEvent/f:entity</sch:title>
    <sch:rule context="f:AuditEvent/f:entity">
      <sch:assert test="count(f:role) &lt;= 0">role: maximum cardinality of 'role' is 0</sch:assert>
      <sch:assert test="count(f:lifecycle) &lt;= 0">lifecycle: maximum cardinality of 'lifecycle' is 0</sch:assert>
      <sch:assert test="count(f:securityLabel) &lt;= 0">securityLabel: maximum cardinality of 'securityLabel' is 0</sch:assert>
      <sch:assert test="count(f:name) &lt;= 0">name: maximum cardinality of 'name' is 0</sch:assert>
      <sch:assert test="count(f:query) &lt;= 0">query: maximum cardinality of 'query' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
</sch:schema>
