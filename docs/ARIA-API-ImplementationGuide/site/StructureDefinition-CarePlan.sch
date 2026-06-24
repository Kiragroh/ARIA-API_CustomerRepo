<?xml version="1.0" encoding="UTF-8"?>
<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2">
  <sch:ns prefix="f" uri="http://hl7.org/fhir"/>
  <sch:ns prefix="h" uri="http://www.w3.org/1999/xhtml"/>
  <!-- 
    This file contains just the constraints for the profile CarePlan
    It includes the base constraints for the resource as well.
    Because of the way that schematrons and containment work, 
    you may need to use this schematron fragment to build a, 
    single schematron that validates contained resources (if you have any) 
  -->
  <sch:pattern>
    <sch:title>f:CarePlan</sch:title>
    <sch:rule context="f:CarePlan">
      <sch:assert test="count(f:id) &gt;= 1">id: minimum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/default']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/default': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/careplan-lastUpdatedOn']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/careplan-lastUpdatedOn': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/careplan-activityAutoAssignOncologist']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/careplan-activityAutoAssignOncologist': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/careplan-activity-definition']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/careplan-activity-definition': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/careplan-lagfrompredecessor']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/careplan-lagfrompredecessor': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:identifier) &lt;= 0">identifier: maximum cardinality of 'identifier' is 0</sch:assert>
      <sch:assert test="count(f:instantiatesCanonical) &lt;= 0">instantiatesCanonical: maximum cardinality of 'instantiatesCanonical' is 0</sch:assert>
      <sch:assert test="count(f:instantiatesUri) &lt;= 0">instantiatesUri: maximum cardinality of 'instantiatesUri' is 0</sch:assert>
      <sch:assert test="count(f:basedOn) &lt;= 0">basedOn: maximum cardinality of 'basedOn' is 0</sch:assert>
      <sch:assert test="count(f:replaces) &lt;= 0">replaces: maximum cardinality of 'replaces' is 0</sch:assert>
      <sch:assert test="count(f:partOf) &lt;= 0">partOf: maximum cardinality of 'partOf' is 0</sch:assert>
      <sch:assert test="count(f:title) &gt;= 1">title: minimum cardinality of 'title' is 1</sch:assert>
      <sch:assert test="count(f:description) &lt;= 0">description: maximum cardinality of 'description' is 0</sch:assert>
      <sch:assert test="count(f:encounter) &lt;= 0">encounter: maximum cardinality of 'encounter' is 0</sch:assert>
      <sch:assert test="count(f:period) &lt;= 0">period: maximum cardinality of 'period' is 0</sch:assert>
      <sch:assert test="count(f:contributor) &lt;= 0">contributor: maximum cardinality of 'contributor' is 0</sch:assert>
      <sch:assert test="count(f:careTeam) &lt;= 0">careTeam: maximum cardinality of 'careTeam' is 0</sch:assert>
      <sch:assert test="count(f:addresses) &lt;= 0">addresses: maximum cardinality of 'addresses' is 0</sch:assert>
      <sch:assert test="count(f:supportingInfo) &lt;= 0">supportingInfo: maximum cardinality of 'supportingInfo' is 0</sch:assert>
      <sch:assert test="count(f:goal) &lt;= 0">goal: maximum cardinality of 'goal' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:CarePlan/f:meta</sch:title>
    <sch:rule context="f:CarePlan/f:meta">
      <sch:assert test="count(f:id) &lt;= 1">id: maximum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:versionId) &lt;= 1">versionId: maximum cardinality of 'versionId' is 1</sch:assert>
      <sch:assert test="count(f:lastUpdated) &lt;= 1">lastUpdated: maximum cardinality of 'lastUpdated' is 1</sch:assert>
      <sch:assert test="count(f:source) &lt;= 1">source: maximum cardinality of 'source' is 1</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:CarePlan/f:activity</sch:title>
    <sch:rule context="f:CarePlan/f:activity">
      <sch:assert test="count(f:id) &gt;= 1">id: minimum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:outcomeCodeableConcept) &lt;= 0">outcomeCodeableConcept: maximum cardinality of 'outcomeCodeableConcept' is 0</sch:assert>
      <sch:assert test="count(f:progress) &lt;= 0">progress: maximum cardinality of 'progress' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:CarePlan/f:activity/f:detail</sch:title>
    <sch:rule context="f:CarePlan/f:activity/f:detail">
      <sch:assert test="count(f:instantiatesCanonical) &lt;= 0">instantiatesCanonical: maximum cardinality of 'instantiatesCanonical' is 0</sch:assert>
      <sch:assert test="count(f:instantiatesUri) &lt;= 0">instantiatesUri: maximum cardinality of 'instantiatesUri' is 0</sch:assert>
      <sch:assert test="count(f:reasonCode) &lt;= 0">reasonCode: maximum cardinality of 'reasonCode' is 0</sch:assert>
      <sch:assert test="count(f:reasonReference) &lt;= 0">reasonReference: maximum cardinality of 'reasonReference' is 0</sch:assert>
      <sch:assert test="count(f:doNotPerform) &lt;= 0">doNotPerform: maximum cardinality of 'doNotPerform' is 0</sch:assert>
      <sch:assert test="count(f:location) &lt;= 0">location: maximum cardinality of 'location' is 0</sch:assert>
      <sch:assert test="count(f:product[x]) &lt;= 0">product[x]: maximum cardinality of 'product[x]' is 0</sch:assert>
      <sch:assert test="count(f:quantity) &lt;= 0">quantity: maximum cardinality of 'quantity' is 0</sch:assert>
      <sch:assert test="count(f:description) &lt;= 0">description: maximum cardinality of 'description' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
</sch:schema>
