<?xml version="1.0" encoding="UTF-8"?>
<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2">
  <sch:ns prefix="f" uri="http://hl7.org/fhir"/>
  <sch:ns prefix="h" uri="http://www.w3.org/1999/xhtml"/>
  <!-- 
    This file contains just the constraints for the profile Device
    It includes the base constraints for the resource as well.
    Because of the way that schematrons and containment work, 
    you may need to use this schematron fragment to build a, 
    single schematron that validates contained resources (if you have any) 
  -->
  <sch:pattern>
    <sch:title>f:Device</sch:title>
    <sch:rule context="f:Device">
      <sch:assert test="count(f:id) &gt;= 1">id: minimum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/schedulable']) &gt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/schedulable': minimum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/schedulable']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/schedulable': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/serviceOrganization']) &gt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/serviceOrganization': minimum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:definition) &lt;= 0">definition: maximum cardinality of 'definition' is 0</sch:assert>
      <sch:assert test="count(f:udiCarrier) &lt;= 0">udiCarrier: maximum cardinality of 'udiCarrier' is 0</sch:assert>
      <sch:assert test="count(f:statusReason) &lt;= 0">statusReason: maximum cardinality of 'statusReason' is 0</sch:assert>
      <sch:assert test="count(f:distinctIdentifier) &lt;= 0">distinctIdentifier: maximum cardinality of 'distinctIdentifier' is 0</sch:assert>
      <sch:assert test="count(f:manufacturer) &lt;= 0">manufacturer: maximum cardinality of 'manufacturer' is 0</sch:assert>
      <sch:assert test="count(f:manufactureDate) &lt;= 0">manufactureDate: maximum cardinality of 'manufactureDate' is 0</sch:assert>
      <sch:assert test="count(f:expirationDate) &lt;= 0">expirationDate: maximum cardinality of 'expirationDate' is 0</sch:assert>
      <sch:assert test="count(f:lotNumber) &lt;= 0">lotNumber: maximum cardinality of 'lotNumber' is 0</sch:assert>
      <sch:assert test="count(f:serialNumber) &lt;= 0">serialNumber: maximum cardinality of 'serialNumber' is 0</sch:assert>
      <sch:assert test="count(f:partNumber) &lt;= 0">partNumber: maximum cardinality of 'partNumber' is 0</sch:assert>
      <sch:assert test="count(f:specialization) &lt;= 0">specialization: maximum cardinality of 'specialization' is 0</sch:assert>
      <sch:assert test="count(f:version) &lt;= 0">version: maximum cardinality of 'version' is 0</sch:assert>
      <sch:assert test="count(f:property) &lt;= 0">property: maximum cardinality of 'property' is 0</sch:assert>
      <sch:assert test="count(f:patient) &lt;= 0">patient: maximum cardinality of 'patient' is 0</sch:assert>
      <sch:assert test="count(f:contact) &lt;= 0">contact: maximum cardinality of 'contact' is 0</sch:assert>
      <sch:assert test="count(f:url) &lt;= 0">url: maximum cardinality of 'url' is 0</sch:assert>
      <sch:assert test="count(f:note) &lt;= 0">note: maximum cardinality of 'note' is 0</sch:assert>
      <sch:assert test="count(f:safety) &lt;= 0">safety: maximum cardinality of 'safety' is 0</sch:assert>
      <sch:assert test="count(f:parent) &lt;= 0">parent: maximum cardinality of 'parent' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:Device/f:meta</sch:title>
    <sch:rule context="f:Device/f:meta">
      <sch:assert test="count(f:id) &lt;= 1">id: maximum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:versionId) &lt;= 1">versionId: maximum cardinality of 'versionId' is 1</sch:assert>
      <sch:assert test="count(f:lastUpdated) &lt;= 1">lastUpdated: maximum cardinality of 'lastUpdated' is 1</sch:assert>
      <sch:assert test="count(f:source) &lt;= 1">source: maximum cardinality of 'source' is 1</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:Device/f:udiCarrier</sch:title>
    <sch:rule context="f:Device/f:udiCarrier">
      <sch:assert test="count(f:deviceIdentifier) &lt;= 0">deviceIdentifier: maximum cardinality of 'deviceIdentifier' is 0</sch:assert>
      <sch:assert test="count(f:issuer) &lt;= 0">issuer: maximum cardinality of 'issuer' is 0</sch:assert>
      <sch:assert test="count(f:jurisdiction) &lt;= 0">jurisdiction: maximum cardinality of 'jurisdiction' is 0</sch:assert>
      <sch:assert test="count(f:carrierAIDC) &lt;= 0">carrierAIDC: maximum cardinality of 'carrierAIDC' is 0</sch:assert>
      <sch:assert test="count(f:carrierHRF) &lt;= 0">carrierHRF: maximum cardinality of 'carrierHRF' is 0</sch:assert>
      <sch:assert test="count(f:entryType) &lt;= 0">entryType: maximum cardinality of 'entryType' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:Device/f:version</sch:title>
    <sch:rule context="f:Device/f:version">
      <sch:assert test="count(f:type) &lt;= 0">type: maximum cardinality of 'type' is 0</sch:assert>
      <sch:assert test="count(f:component) &lt;= 0">component: maximum cardinality of 'component' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:Device/f:property</sch:title>
    <sch:rule context="f:Device/f:property">
      <sch:assert test="count(f:valueQuantity) &lt;= 0">valueQuantity: maximum cardinality of 'valueQuantity' is 0</sch:assert>
      <sch:assert test="count(f:valueCode) &lt;= 0">valueCode: maximum cardinality of 'valueCode' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
</sch:schema>
