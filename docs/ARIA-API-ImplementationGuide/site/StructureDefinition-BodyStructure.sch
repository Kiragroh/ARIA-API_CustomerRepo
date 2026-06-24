<?xml version="1.0" encoding="UTF-8"?>
<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2">
  <sch:ns prefix="f" uri="http://hl7.org/fhir"/>
  <sch:ns prefix="h" uri="http://www.w3.org/1999/xhtml"/>
  <!-- 
    This file contains just the constraints for the profile BodyStructure
    It includes the base constraints for the resource as well.
    Because of the way that schematrons and containment work, 
    you may need to use this schematron fragment to build a, 
    single schematron that validates contained resources (if you have any) 
  -->
  <sch:pattern>
    <sch:title>f:BodyStructure</sch:title>
    <sch:rule context="f:BodyStructure">
      <sch:assert test="count(f:id) &gt;= 1">id: minimum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/daily-dose-limit']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/daily-dose-limit': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/total-dose-limit']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/total-dose-limit': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:extension[@url = 'http://varian.com/fhir/v1/StructureDefinition/session-dose-limit']) &lt;= 1">extension with URL = 'http://varian.com/fhir/v1/StructureDefinition/session-dose-limit': maximum cardinality of 'extension' is 1</sch:assert>
      <sch:assert test="count(f:active) &lt;= 0">active: maximum cardinality of 'active' is 0</sch:assert>
      <sch:assert test="count(f:location) &lt;= 0">location: maximum cardinality of 'location' is 0</sch:assert>
      <sch:assert test="count(f:locationQualifier) &lt;= 0">locationQualifier: maximum cardinality of 'locationQualifier' is 0</sch:assert>
      <sch:assert test="count(f:description) &lt;= 0">description: maximum cardinality of 'description' is 0</sch:assert>
      <sch:assert test="count(f:image) &lt;= 0">image: maximum cardinality of 'image' is 0</sch:assert>
    </sch:rule>
  </sch:pattern>
  <sch:pattern>
    <sch:title>f:BodyStructure/f:meta</sch:title>
    <sch:rule context="f:BodyStructure/f:meta">
      <sch:assert test="count(f:id) &lt;= 1">id: maximum cardinality of 'id' is 1</sch:assert>
      <sch:assert test="count(f:versionId) &lt;= 1">versionId: maximum cardinality of 'versionId' is 1</sch:assert>
      <sch:assert test="count(f:lastUpdated) &lt;= 1">lastUpdated: maximum cardinality of 'lastUpdated' is 1</sch:assert>
      <sch:assert test="count(f:source) &lt;= 1">source: maximum cardinality of 'source' is 1</sch:assert>
    </sch:rule>
  </sch:pattern>
</sch:schema>
