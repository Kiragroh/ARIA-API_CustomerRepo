(function attachHelpers(root) {
  function compact(values) {
    return values.map((value) => String(value || "").trim()).filter(Boolean)
  }

  function resourcePayload(result) {
    return result?.response?.json || result?.json || result || null
  }

  function resourcesFromResult(result) {
    const payload = resourcePayload(result)
    if (!payload) return []
    if (payload.resourceType === "Bundle") {
      return (payload.entry || []).map((entry) => entry?.resource).filter(Boolean)
    }
    return payload.resourceType ? [payload] : []
  }

  function codeText(codeableConcept) {
    const coding = codeableConcept?.coding || []
    const primary = coding.find((item) => item?.display || item?.code) || {}
    return compact([primary.display, primary.code && primary.display !== primary.code ? primary.code : ""]).join(" / ")
  }

  function humanName(resource) {
    const names = resource?.name || []
    const first = Array.isArray(names) ? names[0] : names
    if (!first) return ""
    if (first.text) return first.text
    return compact([...(first.given || []), first.family]).join(" ")
  }

  function identifierValues(resource) {
    const identifiers = Array.isArray(resource?.identifier) ? resource.identifier : []
    return compact(identifiers.map((item) => item?.value || item?.id))
  }

  function patientReference(resource) {
    if (resource?.subject?.reference) return resource.subject.reference
    if (resource?.patient?.reference) return resource.patient.reference
    const participant = (resource?.participant || []).find((item) => item?.actor?.reference?.startsWith("Patient/"))
    if (participant) return participant.actor.reference
    const performers = resource?.performer || []
    const performer = performers.find((item) => item?.actor?.reference?.startsWith("Patient/"))
    if (performer) return performer.actor.reference
    return ""
  }

  function dateText(resource) {
    if (!resource) return ""
    if (resource.resourceType === "Appointment") {
      return compact([resource.start, resource.end]).join(" bis ")
    }
    return (
      resource.date ||
      resource.authoredOn ||
      resource.issued ||
      resource.effectiveDateTime ||
      resource.performedDateTime ||
      resource.recordedDate ||
      resource.onsetDateTime ||
      resource.birthDate ||
      ""
    )
  }

  function titleText(resource) {
    if (!resource) return ""
    if (resource.resourceType === "DocumentReference") {
      return resource.description || codeText(resource.type) || resource.docStatus || resource.status || ""
    }
    if (resource.resourceType === "Appointment") {
      return compact([resource.status, resource.description]).join(" - ")
    }
    if (resource.resourceType === "Patient") return humanName(resource) || resource.gender || ""
    if (resource.resourceType === "Practitioner") return humanName(resource) || ""
    if (resource.resourceType === "Organization" || resource.resourceType === "Location") {
      return resource.name || resource.alias?.[0] || resource.status || ""
    }
    return (
      resource.title ||
      resource.name ||
      resource.description ||
      codeText(resource.code) ||
      codeText(resource.type) ||
      resource.status ||
      resource.resourceType ||
      ""
    )
  }

  function rowFromResource(resource, options = {}) {
    return {
      key: `${resource?.resourceType || "Resource"}/${resource?.id || cryptoKey()}`,
      queryLabel: options.queryLabel || "",
      resource,
      resourceType: resource?.resourceType || "",
      fhirId: resource?.id || "",
      identifierText: identifierValues(resource).join(" | "),
      dateText: dateText(resource),
      titleText: titleText(resource),
      patientText: patientReference(resource),
    }
  }

  function rowsFromFhirResult(result, options = {}) {
    return resourcesFromResult(result).map((resource) => rowFromResource(resource, options))
  }

  function cryptoKey() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID()
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`
  }

  function ensureCoding(resource) {
    resource.type = resource.type || {}
    resource.type.coding = Array.isArray(resource.type.coding) ? resource.type.coding : [{}]
    if (!resource.type.coding.length) resource.type.coding.push({})
    return resource.type.coding[0]
  }

  function ensureAppointmentPatient(resource) {
    resource.participant = Array.isArray(resource.participant) ? resource.participant : []
    let participant = resource.participant.find((item) => item?.actor?.reference?.startsWith("Patient/"))
    if (!participant) {
      participant = { actor: { reference: "" }, status: "accepted" }
      resource.participant.unshift(participant)
    }
    participant.actor = participant.actor || {}
    return participant
  }

  function applyQuickFields(resource, fields) {
    if (!resource || !fields) return resource
    if ("status" in fields) resource.status = fields.status
    if ("description" in fields) resource.description = fields.description

    if (resource.resourceType === "DocumentReference") {
      if ("docStatus" in fields) resource.docStatus = fields.docStatus
      if ("date" in fields) resource.date = fields.date
      if ("patientReference" in fields) {
        resource.subject = resource.subject || {}
        resource.subject.reference = fields.patientReference
      }
      if ("typeCode" in fields || "typeDisplay" in fields || "typeSystem" in fields) {
        const coding = ensureCoding(resource)
        if ("typeCode" in fields) coding.code = fields.typeCode
        if ("typeDisplay" in fields) coding.display = fields.typeDisplay
        if ("typeSystem" in fields && fields.typeSystem) coding.system = fields.typeSystem
      }
    }

    if (resource.resourceType === "Appointment") {
      if ("start" in fields) resource.start = fields.start
      if ("end" in fields) resource.end = fields.end
      if ("patientReference" in fields) {
        const participant = ensureAppointmentPatient(resource)
        participant.actor.reference = fields.patientReference
      }
    }

    if ("active" in fields && "active" in resource) resource.active = fields.active
    if ("name" in fields && "name" in resource) resource.name = fields.name
    return resource
  }

  function buildRecentParams(options = {}) {
    const params = { _count: String(options.count || "20") || "20" }
    if (options.sort) params._sort = options.sort
    return params
  }

  const api = {
    applyQuickFields,
    buildRecentParams,
    codeText,
    dateText,
    identifierValues,
    patientReference,
    resourcesFromResult,
    rowFromResource,
    rowsFromFhirResult,
    titleText,
  }

  if (typeof module === "object" && module.exports) module.exports = api
  root.FhirTesterHelpers = api
})(typeof globalThis !== "undefined" ? globalThis : window)
