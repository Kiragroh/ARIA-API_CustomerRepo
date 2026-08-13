<?xml version="1.0" encoding="UTF-8"?>
<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2">
  <sch:ns prefix="f" uri="http://hl7.org/fhir"/>
  <sch:ns prefix="h" uri="http://www.w3.org/1999/xhtml"/>
  <!-- 
    This file contains just the constraints for the profile ChargeItem
    It includes the base constraints for the resource as well.
    Because of the way that schematrons and containment work, 
    you may need to use this schematron fragment to build a, 
    single schematron that validates contained resources (if you have any) 
  -->
  <sch:pattern>
    <sch:title>f:ChargeItem</sch:title>
    <sch:rule context="f:ChargeItem">
      <sch:assert test="count(f:id) &gt;= 1">id: minimum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:implicitRules) &lt;= 0">implicitRules: maximum cardinality of 'implicitRules' is 0</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/chargeItem-associateCharge']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/chargeItem-associateCharge': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/chargeitem-category']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/chargeitem-category': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/chargeitem-completedOn']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/chargeitem-completedOn': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:partOf) &lt;= 0">partOf: maximum cardinality of 'partOf' is 0</sch:assert>
      <sch:assert test="count(f:context) &lt;= 0">context: maximum cardinality of 'context' is 0</sch:assert>
      <sch:assert test="count(f:requestingOrganization) &lt;= 0">requestingOrganization: maximum cardinality of 'requestingOrganization' is 0</sch:assert>
      <sch:assert test="count(f:bodysite) &lt;= 0">bodysite: maximum cardinality of 'bodysite' is 0</sch:assert>
      <sch:assert test="count(f:service) &lt;= 0">service: maximum cardinality of 'service' is 0</sch:assert>
      <sch:assert test="count(f:product[x]) &lt;= 0">product[x]: maximum cardinality of 'product[x]' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:ChargeItem/f:meta</sch:title>
    <sch:rule context="f:ChargeItem/f:meta">
      <sch:assert test="count(f:id) &lt;= 1">id: maximum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:versionId) &lt;= 1">versionId: maximum cardinality of 'versionId' is 1</sch:assert>
      <sch:assert test="count(f:lastUpdated) &lt;= 1">lastUpdated: maximum cardinality of 'lastUpdated' is 1</sch:assert>
      <sch:assert test="count(f:source) &lt;= 1">source: maximum cardinality of 'source' is 1</sch:assert>
    </sch:rule>
  </sch:pattern>
</sch:schema>
