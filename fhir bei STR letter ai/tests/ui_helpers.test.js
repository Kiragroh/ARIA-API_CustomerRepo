const assert = require("node:assert/strict")
const helpers = require("../web/ui_helpers.js")

const docBundle = {
  response: {
    json: {
      resourceType: "Bundle",
      entry: [
        {
          resource: {
            resourceType: "DocumentReference",
            id: "DocumentReference-42",
            identifier: [
              { system: "urn:aria:doc", value: "DOC-4711" },
              { value: "SCAN-7" },
            ],
            subject: { reference: "Patient/Patient-123" },
            date: "2026-06-08T10:15:00Z",
            status: "current",
            docStatus: "preliminary",
            description: "Nachsorgebrief",
            type: {
              coding: [{ code: "1055", display: "Nachsorgebrief" }],
            },
          },
        },
      ],
    },
  },
}

const appointment = {
  resourceType: "Appointment",
  id: "Appointment-99",
  identifier: [{ value: "APT-99" }],
  status: "booked",
  start: "2026-06-09T08:00:00Z",
  end: "2026-06-09T08:30:00Z",
  description: "Erstgespraech",
  participant: [{ actor: { reference: "Patient/Patient-123" } }],
}

{
  const rows = helpers.rowsFromFhirResult(docBundle, { queryLabel: "Dokumente" })
  assert.equal(rows.length, 1)
  assert.equal(rows[0].resourceType, "DocumentReference")
  assert.equal(rows[0].fhirId, "DocumentReference-42")
  assert.equal(rows[0].identifierText, "DOC-4711 | SCAN-7")
  assert.equal(rows[0].patientText, "Patient/Patient-123")
  assert.equal(rows[0].dateText, "2026-06-08T10:15:00Z")
  assert.equal(rows[0].titleText, "Nachsorgebrief")
}

{
  const row = helpers.rowFromResource(appointment)
  assert.equal(row.resourceType, "Appointment")
  assert.equal(row.fhirId, "Appointment-99")
  assert.equal(row.identifierText, "APT-99")
  assert.equal(row.patientText, "Patient/Patient-123")
  assert.equal(row.dateText, "2026-06-09T08:00:00Z bis 2026-06-09T08:30:00Z")
  assert.equal(row.titleText, "booked - Erstgespraech")
}

{
  const resource = structuredClone(appointment)
  helpers.applyQuickFields(resource, {
    status: "cancelled",
    start: "2026-06-10T07:00:00Z",
    end: "2026-06-10T07:20:00Z",
    description: "Kontrolle",
    patientReference: "Patient/Patient-777",
  })
  assert.equal(resource.status, "cancelled")
  assert.equal(resource.start, "2026-06-10T07:00:00Z")
  assert.equal(resource.end, "2026-06-10T07:20:00Z")
  assert.equal(resource.description, "Kontrolle")
  assert.equal(resource.participant[0].actor.reference, "Patient/Patient-777")
}

{
  const resource = structuredClone(docBundle.response.json.entry[0].resource)
  helpers.applyQuickFields(resource, {
    status: "superseded",
    docStatus: "final",
    date: "2026-06-08T12:00:00Z",
    description: "Geaendert",
    typeCode: "1034",
    typeDisplay: "Arztbriefe (intern)",
    patientReference: "Patient/Patient-555",
  })
  assert.equal(resource.status, "superseded")
  assert.equal(resource.docStatus, "final")
  assert.equal(resource.date, "2026-06-08T12:00:00Z")
  assert.equal(resource.description, "Geaendert")
  assert.equal(resource.type.coding[0].code, "1034")
  assert.equal(resource.type.coding[0].display, "Arztbriefe (intern)")
  assert.equal(resource.subject.reference, "Patient/Patient-555")
}

{
  assert.deepEqual(helpers.buildRecentParams({ count: "20", sort: "-date" }), {
    _count: "20",
    _sort: "-date",
  })
  assert.deepEqual(helpers.buildRecentParams({ count: "", sort: "" }), {
    _count: "20",
  })
}
