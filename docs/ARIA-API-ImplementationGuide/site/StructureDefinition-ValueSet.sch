<?xml version="1.0" encoding="UTF-8"?>
<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2">
  <sch:ns prefix="f" uri="http://hl7.org/fhir"/>
  <sch:ns prefix="h" uri="http://www.w3.org/1999/xhtml"/>
  <!-- 
    This file contains just the constraints for the profile ValueSet
    It includes the base constraints for the resource as well.
    Because of the way that schematrons and containment work, 
    you may need to use this schematron fragment to build a, 
    single schematron that validates contained resources (if you have any) 
  -->
  <sch:pattern>
    <sch:title>f:ValueSet</sch:title>
    <sch:rule context="f:ValueSet">
      <sch:assert test="count(f:id) &gt;= 1">id: minimum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:identifier) &lt;= 0">identifier: maximum cardinality of 'identifier' is 0</sch:assert>
      <sch:assert test="count(f:title) &lt;= 0">title: maximum cardinality of 'title' is 0</sch:assert>
      <sch:assert test="count(f:experimental) &lt;= 0">experimental: maximum cardinality of 'experimental' is 0</sch:assert>
      <sch:assert test="count(f:date) &lt;= 0">date: maximum cardinality of 'date' is 0</sch:assert>
      <sch:assert test="count(f:contact) &lt;= 0">contact: maximum cardinality of 'contact' is 0</sch:assert>
      <sch:assert test="count(f:jurisdiction) &lt;= 0">jurisdiction: maximum cardinality of 'jurisdiction' is 0</sch:assert>
      <sch:assert test="count(f:immutable) &lt;= 0">immutable: maximum cardinality of 'immutable' is 0</sch:assert>
      <sch:assert test="count(f:purpose) &lt;= 0">purpose: maximum cardinality of 'purpose' is 0</sch:assert>
      <sch:assert test="count(f:copyright) &lt;= 0">copyright: maximum cardinality of 'copyright' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:ValueSet/f:compose</sch:title>
    <sch:rule context="f:ValueSet/f:compose">
      <sch:assert test="count(f:lockedDate) &lt;= 0">lockedDate: maximum cardinality of 'lockedDate' is 0</sch:assert>
      <sch:assert test="count(f:inactive) &lt;= 0">inactive: maximum cardinality of 'inactive' is 0</sch:assert>
      <sch:assert test="count(f:exclude) &lt;= 0">exclude: maximum cardinality of 'exclude' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:ValueSet/f:compose/f:include</sch:title>
    <sch:rule context="f:ValueSet/f:compose/f:include">
      <sch:assert test="count(f:version) &lt;= 0">version: maximum cardinality of 'version' is 0</sch:assert>
      <sch:assert test="count(f:filter) &lt;= 0">filter: maximum cardinality of 'filter' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:ValueSet/f:compose/f:include/f:concept</sch:title>
    <sch:rule context="f:ValueSet/f:compose/f:include/f:concept">
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/valueset-payor-plan-type']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/valueset-payor-plan-type': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/valueset-Required']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/valueset-Required': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/directive-userConfirmationRequired']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/directive-userConfirmationRequired': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:designation) &lt;= 0">designation: maximum cardinality of 'designation' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:ValueSet/f:expansion</sch:title>
    <sch:rule context="f:ValueSet/f:expansion">
      <sch:assert test="count(f:identifier) &lt;= 0">identifier: maximum cardinality of 'identifier' is 0</sch:assert>
      <sch:assert test="count(f:total) &lt;= 0">total: maximum cardinality of 'total' is 0</sch:assert>
      <sch:assert test="count(f:offset) &lt;= 0">offset: maximum cardinality of 'offset' is 0</sch:assert>
      <sch:assert test="count(f:parameter) &lt;= 0">parameter: maximum cardinality of 'parameter' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:ValueSet/f:expansion/f:contains</sch:title>
    <sch:rule context="f:ValueSet/f:expansion/f:contains">
      <sch:assert test="count(f:abstract) &lt;= 0">abstract: maximum cardinality of 'abstract' is 0</sch:assert>
      <sch:assert test="count(f:inactive) &lt;= 0">inactive: maximum cardinality of 'inactive' is 0</sch:assert>
      <sch:assert test="count(f:version) &lt;= 0">version: maximum cardinality of 'version' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
</sch:schema>
