const helpers = window.FhirTesterHelpers

const state = {
  settings: {},
  docTypes: [],
  currentRows: [],
  history: [],
  selected: null,
  selectedResourcePage: null,
}

const $ = (id) => document.getElementById(id)

function pretty(value) {
  return JSON.stringify(value, null, 2)
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;")
}

function readSecret() {
  return $("clientSecret").value.trim()
}

function scopeValue() {
  return $("scope").value.trim()
}

function writeOptions() {
  return {
    confirm_write: $("confirmWrite").checked,
    confirmation_phrase: $("confirmationPhrase").value,
  }
}

function publicRequest(value) {
  if (!value || typeof value !== "object") return value
  const copyValue = clone(value)
  if (copyValue.client_secret) copyValue.client_secret = "***"
  if (copyValue.body?.content?.[0]?.attachment?.data) {
    copyValue.body.content[0].attachment.data = "<base64>"
  }
  return copyValue
}

function showRequest(value) {
  $("requestBox").textContent = typeof value === "string" ? value : pretty(publicRequest(value))
}

function showResponse(value) {
  $("responseBox").textContent = typeof value === "string" ? value : pretty(value)
}

function showError(err) {
  const message = String(err?.message || err)
  showResponse({ ok: false, error: message })
  $("resultsSummary").textContent = message
}

function setTokenStatus(result) {
  const box = $("tokenStatus")
  box.className = `status ${result.ok ? "ok" : "bad"}`
  if (result.ok) {
    box.textContent = `OK ${result.status_code}, ${result.token_type}, expires ${result.expires_in}s\nScope: ${result.returned_scope || "(leer)"}`
  } else {
    box.textContent = `Fehler ${result.status_code || ""}: ${typeof result.error === "string" ? result.error : pretty(result.error)}`
  }
}

async function api(path, body = null, method = "POST") {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  }
  if (body !== null) options.body = JSON.stringify(body)
  const res = await fetch(path, options)
  const text = await res.text()
  let payload
  try {
    payload = text ? JSON.parse(text) : null
  } catch {
    payload = text
  }
  if (!res.ok) {
    const detail = payload?.detail ?? payload
    throw new Error(typeof detail === "string" ? detail : pretty(detail))
  }
  return payload
}

function fhirBody(method, path, params = {}, body = null) {
  return {
    method,
    path,
    params,
    body,
    scope: scopeValue(),
    client_secret: readSecret(),
    ...writeOptions(),
  }
}

function renderHistory() {
  const body = $("historyBody")
  if (!state.history.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">Noch kein Verlauf.</td></tr>`
    return
  }
  body.innerHTML = state.history
    .map((entry, index) => {
      const row = entry.row
      const id = row?.fhirId || ""
      const identifier = row?.identifierText || ""
      const patient = row?.patientText || ""
      const action = row
        ? `<button class="mini" data-history-open="${index}">Öffnen</button>`
        : `<span class="hint">keine Resource</span>`
      return `<tr>
        <td>${escapeHtml(entry.time)}</td>
        <td>${escapeHtml(entry.label)}</td>
        <td>${id ? `<button class="copy-value" data-history-copy="${index}" data-field="fhirId">${escapeHtml(id)}</button>` : ""}</td>
        <td>${identifier ? `<button class="copy-value" data-history-copy="${index}" data-field="identifierText">${escapeHtml(identifier)}</button>` : ""}</td>
        <td>${escapeHtml(patient)}</td>
        <td>${action}</td>
      </tr>`
    })
    .join("")
}

function addHistory(label, rows) {
  const time = new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
  const entries = rows.length
    ? rows.map((row) => ({ time, label, row }))
    : [{ time, label, row: null }]
  state.history = [...entries, ...state.history].slice(0, 200)
  renderHistory()
}

function renderResults(summary = "") {
  const body = $("resultsBody")
  if (!state.currentRows.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">Keine Treffer.</td></tr>`
    $("resultsSummary").textContent = summary || "Keine Treffer geladen."
    return
  }
  $("resultsSummary").textContent = `${summary || `${state.currentRows.length} Treffer geladen.`} Zeile öffnet den Eintrag.`
  body.innerHTML = state.currentRows
    .map(
      (row, index) => `<tr data-row-index="${index}">
        <td>${escapeHtml(row.resourceType)}</td>
        <td>${row.fhirId ? `<button class="copy-value" data-copy-row="${index}" data-field="fhirId">${escapeHtml(row.fhirId)}</button>` : ""}</td>
        <td>${row.identifierText ? `<button class="copy-value" data-copy-row="${index}" data-field="identifierText">${escapeHtml(row.identifierText)}</button>` : ""}</td>
        <td>${escapeHtml(row.dateText)}</td>
        <td>${escapeHtml(row.titleText)}</td>
        <td>${escapeHtml(row.patientText)}</td>
      </tr>`
    )
    .join("")
}

function handleFhirResult(result, label, options = {}) {
  const rows = helpers.rowsFromFhirResult(result, { queryLabel: label })
  addHistory(label, rows)
  if (options.renderResults !== false) {
    state.currentRows = rows
    const status = result?.ok === false ? `FHIR-Fehler ${result.status_code || ""}` : ""
    renderResults(rows.length ? `${rows.length} Treffer aus ${label}.` : `${status || "Keine Resource"} aus ${label}.`)
  }
  return rows
}

async function runFhir(method, path, params = {}, body = null, options = {}) {
  const req = fhirBody(method, path, params, body)
  showRequest(req)
  const label = options.label || `${method} ${path}`
  try {
    const result = await api("/api/fhir", req)
    showResponse(result)
    handleFhirResult(result, label, options)
    return result
  } catch (err) {
    showError(err)
    addHistory(`${label} (Fehler)`, [])
    throw err
  }
}

async function runResourceSearch(resource, params, label) {
  const result = await runFhir("GET", resource, params, null, { label })
  if (result?.ok === false && params._sort) {
    const fallback = { ...params }
    delete fallback._sort
    return runFhir("GET", resource, fallback, null, { label: `${label} ohne Sortierung` })
  }
  return result
}

function parseJsonBox(id, fallback = null) {
  const text = $(id).value.trim()
  if (!text) return fallback
  return JSON.parse(text)
}

function firstResource(result) {
  return helpers.resourcesFromResult(result)[0] || null
}

async function copyText(text) {
  const value = String(text || "")
  if (!value) return
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return
  }
  const textarea = document.createElement("textarea")
  textarea.value = value
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand("copy")
  textarea.remove()
}

function pageByResource(resource) {
  return (state.settings.resource_pages || []).find((page) => page.resource === resource) || null
}

function activePage() {
  const tab = document.querySelector(".tab.active")?.dataset.tab
  if (tab === "documents") return pageByResource("DocumentReference")
  if (tab === "appointments") return pageByResource("Appointment")
  if (tab === "resources") return state.selectedResourcePage
  return null
}

function applyPageScope(kind) {
  const page = activePage()
  if (!page) return
  const value = kind === "write" ? page.write_scope : page.read_scope
  if (value) $("scope").value = value
}

function selectField(field, value, options) {
  const existing = new Set(options)
  if (value && !existing.has(value)) options = [value, ...options]
  const opts = options
    .map((option) => `<option value="${escapeHtml(option)}"${option === value ? " selected" : ""}>${escapeHtml(option || "(leer)")}</option>`)
    .join("")
  return `<select data-field="${escapeHtml(field)}">${opts}</select>`
}

function textField(label, field, value, type = "text") {
  return `<label>${escapeHtml(label)}<input data-field="${escapeHtml(field)}" type="${type}" value="${escapeHtml(value || "")}" /></label>`
}

function renderQuickEditor(resource) {
  const box = $("quickEditor")
  if (!resource) {
    box.innerHTML = `<div class="hint">Öffne einen Treffer, um Felder zu bearbeiten.</div>`
    return
  }

  if (resource.resourceType === "DocumentReference") {
    const coding = resource.type?.coding?.[0] || {}
    box.innerHTML = `<div class="quick-grid">
      <label>Status${selectField("status", resource.status || "", ["current", "superseded", "entered-in-error"])}</label>
      <label>DocStatus${selectField("docStatus", resource.docStatus || "", ["preliminary", "final", "amended", "entered-in-error"])}</label>
      ${textField("Datum/Zeit", "date", resource.date || "")}
      ${textField("Patient", "patientReference", resource.subject?.reference || "")}
      ${textField("Beschreibung", "description", resource.description || "")}
      ${textField("Typ-Code", "typeCode", coding.code || "")}
      ${textField("Typ-Anzeige", "typeDisplay", coding.display || "")}
      ${textField("Typ-System", "typeSystem", coding.system || "")}
    </div>`
    return
  }

  if (resource.resourceType === "Appointment") {
    box.innerHTML = `<div class="quick-grid">
      <label>Status${selectField("status", resource.status || "", [
        "proposed",
        "pending",
        "booked",
        "arrived",
        "fulfilled",
        "cancelled",
        "noshow",
        "entered-in-error",
        "checked-in",
        "waitlist",
      ])}</label>
      ${textField("Start", "start", resource.start || "")}
      ${textField("Ende", "end", resource.end || "")}
      ${textField("Patient", "patientReference", helpers.patientReference(resource))}
      ${textField("Beschreibung", "description", resource.description || "")}
    </div>`
    return
  }

  const fields = []
  if ("status" in resource) fields.push(`<label>Status${selectField("status", resource.status || "", [resource.status || "", "active", "inactive", "completed", "cancelled", "entered-in-error"])}</label>`)
  if ("active" in resource) {
    fields.push(`<label class="check inline"><input data-field="active" type="checkbox"${resource.active ? " checked" : ""} /> Aktiv</label>`)
  }
  if (typeof resource.name === "string") fields.push(textField("Name", "name", resource.name))
  if ("description" in resource) fields.push(textField("Beschreibung", "description", resource.description || ""))
  box.innerHTML = fields.length
    ? `<div class="quick-grid">${fields.join("")}</div>`
    : `<div class="hint">Für diese Resource bitte das JSON bearbeiten.</div>`
}

function quickFields() {
  const fields = {}
  document.querySelectorAll("#quickEditor [data-field]").forEach((input) => {
    if (input.type === "checkbox") {
      fields[input.dataset.field] = input.checked
    } else {
      fields[input.dataset.field] = input.value
    }
  })
  return fields
}

function openRow(row) {
  if (!row?.resource) return
  const resource = clone(row.resource)
  state.selected = helpers.rowFromResource(resource, { queryLabel: row.queryLabel })
  $("resourceEditor").value = pretty(resource)
  $("selectedSummary").textContent = `${state.selected.resourceType}/${state.selected.fhirId || "(ohne ID)"} | Identifier: ${state.selected.identifierText || "-"}`
  $("resourceReadId").value = state.selected.fhirId || ""
  renderQuickEditor(resource)
}

function selectedResourceFromEditor() {
  const resource = parseJsonBox("resourceEditor", null)
  if (!resource?.resourceType) throw new Error("Im JSON fehlt resourceType.")
  helpers.applyQuickFields(resource, quickFields())
  $("resourceEditor").value = pretty(resource)
  return resource
}

async function updateSelected() {
  const resource = selectedResourceFromEditor()
  const id = resource.id || state.selected?.fhirId
  if (!id) throw new Error("FHIR-ID fehlt. Ohne ID ist kein PUT möglich.")
  const result = await runFhir("PUT", `${resource.resourceType}/${id}`, {}, resource, { label: `PUT ${resource.resourceType}/${id}` })
  const updated = firstResource(result)
  if (updated) openRow(helpers.rowFromResource(updated))
}

async function reloadSelected() {
  const resourceType = state.selected?.resourceType
  const id = state.selected?.fhirId || parseJsonBox("resourceEditor", {})?.id
  if (!resourceType || !id) throw new Error("Öffne zuerst einen Eintrag mit FHIR-ID.")
  const result = await runFhir("GET", `${resourceType}/${id}`, {}, null, { label: `GET ${resourceType}/${id}` })
  const resource = firstResource(result)
  if (resource) openRow(helpers.rowFromResource(resource))
}

async function deleteSelected() {
  const resource = selectedResourceFromEditor()
  const id = resource.id || state.selected?.fhirId
  if (!resource.resourceType || !id) throw new Error("ResourceType oder FHIR-ID fehlt.")
  const ok = window.confirm(`${resource.resourceType}/${id} wirklich live löschen?`)
  if (!ok) return
  await runFhir("DELETE", `${resource.resourceType}/${id}`, {}, null, { label: `DELETE ${resource.resourceType}/${id}` })
}

function docRefCreateTemplate() {
  return {
    resourceType: "DocumentReference",
    status: "current",
    docStatus: "preliminary",
    subject: { reference: "Patient/Patient-..." },
    date: new Date().toISOString(),
    description: "FHIR Tester Dokument",
    type: {
      coding: [
        {
          system: "http://varian.com/fhir/CodeSystem/DocumentReference/documentreference-type",
          code: "1034",
          display: "Arztbriefe (intern)",
        },
      ],
    },
    category: [{ coding: [{ code: "Patient Document", display: "Patient Document" }] }],
    extension: [
      {
        url: "http://varian.com/fhir/v1/StructureDefinition/documentreference-templateName",
        valueString: "FHIR Tester",
      },
      {
        url: "http://varian.com/fhir/v1/StructureDefinition/documentreference-documentLocation",
        valueString: "file-server",
      },
    ],
    content: [
      {
        attachment: {
          contentType: "text/plain",
          data: btoa("FHIR Tester"),
          title: "fhir-tester.txt",
          creation: new Date().toISOString(),
        },
      },
    ],
  }
}

function appointmentTemplate() {
  const start = new Date(Date.now() + 24 * 60 * 60 * 1000)
  start.setMinutes(0, 0, 0)
  const end = new Date(start.getTime() + 30 * 60 * 1000)
  return {
    resourceType: "Appointment",
    status: "booked",
    start: start.toISOString(),
    end: end.toISOString(),
    description: "FHIR Tester Termin",
    participant: [{ actor: { reference: "Patient/Patient-..." }, status: "accepted" }],
  }
}

function genericTemplate() {
  const page = state.selectedResourcePage
  if (!page) return {}
  return { resourceType: page.resource }
}

async function resolvePatient(identifierId, fhirIdId, render = true) {
  const req = {
    patient_identifier: $(identifierId).value.trim(),
    patient_fhir_id: $(fhirIdId).value.trim(),
    scope: scopeValue(),
    client_secret: readSecret(),
  }
  showRequest(req)
  const result = await api("/api/patient/resolve", req)
  showResponse(result)
  if (render) handleFhirResult(result, "Patient auflösen")
  const patient = firstResource(result)
  if (patient?.id) $(fhirIdId).value = patient.id
  return patient
}

function patientParamValue(id) {
  if (!id) return ""
  return `Patient/${id.replace(/^Patient\//, "")}`
}

async function loadRecentDocuments() {
  const params = helpers.buildRecentParams({ count: $("docCount").value || "20", sort: "-date" })
  await runResourceSearch("DocumentReference", params, "DocumentReference letzte 20")
}

async function searchDocuments() {
  let patient = $("docPatientFhirId").value.trim()
  if (!patient && $("docPatientIdentifier").value.trim()) {
    const resolved = await resolvePatient("docPatientIdentifier", "docPatientFhirId", false)
    patient = resolved?.id || ""
  }
  const params = helpers.buildRecentParams({ count: $("docCount").value || "20", sort: "-date" })
  if (patient) params.patient = patientParamValue(patient)
  if ($("docTypeSelect").value) params.type = $("docTypeSelect").value
  await runResourceSearch("DocumentReference", params, "DocumentReference Suche")
}

async function loadRecentAppointments() {
  const params = helpers.buildRecentParams({ count: $("apptCount").value || "20", sort: "-date" })
  await runResourceSearch("Appointment", params, "Appointment letzte 20")
}

async function searchAppointments() {
  let patient = $("apptPatientFhirId").value.trim()
  if (!patient && $("apptPatientIdentifier").value.trim()) {
    const resolved = await resolvePatient("apptPatientIdentifier", "apptPatientFhirId", false)
    patient = resolved?.id || ""
  }
  const params = helpers.buildRecentParams({ count: $("apptCount").value || "20", sort: "-date" })
  if (patient) params.patient = patientParamValue(patient)
  if ($("apptDate").value) params.date = $("apptDate").value
  await runResourceSearch("Appointment", params, "Appointment Suche")
}

function renderDocTypes() {
  const filter = $("docTypeFilter").value.trim().toLowerCase()
  const items = state.docTypes.filter((item) => {
    if (!filter) return true
    return `${item.code} ${item.display} ${item.system}`.toLowerCase().includes(filter)
  })
  $("docTypesList").innerHTML = items.length
    ? items
        .map(
          (item) => `<div class="list-item">
            <button class="copy-value code-pill" data-doc-type-code="${escapeHtml(item.code)}">${escapeHtml(item.code)}</button>
            <span>${escapeHtml(item.display)}<br><span class="hint">${escapeHtml(item.system)}</span></span>
          </div>`
        )
        .join("")
    : `<div class="list-item"><span></span><span class="hint">Keine Treffer.</span></div>`

  const select = $("docTypeSelect")
  const current = select.value
  select.innerHTML = `<option value="">Alle Typen</option>` +
    state.docTypes
      .map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.code)} - ${escapeHtml(item.display)}</option>`)
      .join("")
  select.value = current
}

async function loadDocTypes() {
  const req = {
    publisher: $("docTypePublisher").value.trim(),
    scope: scopeValue(),
    client_secret: readSecret(),
  }
  showRequest(req)
  const result = await api("/api/documentreference/types", req)
  state.docTypes = result.document_types || []
  renderDocTypes()
  showResponse(result)
  addHistory(`DocTypes (${state.docTypes.length})`, [])
}

function renderResourceCards() {
  const cards = $("resourceCards")
  const pages = state.settings.resource_pages || []
  cards.innerHTML = pages
    .map((page) => {
      const selected = state.selectedResourcePage?.resource === page.resource ? " selected" : ""
      return `<div class="resource-card${selected}" data-resource="${escapeHtml(page.resource)}">
        <div>
          <strong>${escapeHtml(page.title || page.resource)}</strong>
          <span>${escapeHtml(page.resource)}</span>
        </div>
        <div class="button-row">
          <button class="mini" data-resource-action="select" data-resource="${escapeHtml(page.resource)}">Öffnen</button>
          <button class="mini" data-resource-action="readScope" data-resource="${escapeHtml(page.resource)}">Read-Scope</button>
          <button class="mini" data-resource-action="load" data-resource="${escapeHtml(page.resource)}">20 laden</button>
        </div>
      </div>`
    })
    .join("")
}

function selectResourcePage(resource) {
  const page = pageByResource(resource)
  if (!page) return
  state.selectedResourcePage = page
  $("resourceTitle").textContent = `${page.title || page.resource} testen`
  $("resourceNeed").textContent = `Read: ${page.read_scope || "-"} | Write: ${page.write_scope || "-"}`
  $("resourceReadId").placeholder = `${page.resource}-...`
  $("resourceParams").value = "{}"
  $("resourceCreate").value = pretty({ resourceType: page.resource })
  renderResourceCards()
}

async function selectedResourceParams() {
  const page = state.selectedResourcePage
  if (!page) throw new Error("Wähle zuerst eine Resource-Seite.")
  let patient = $("resourcePatientFhirId").value.trim()
  if (!patient && $("resourcePatientIdentifier").value.trim()) {
    const resolved = await resolvePatient("resourcePatientIdentifier", "resourcePatientFhirId", false)
    patient = resolved?.id || ""
  }
  const params = {
    ...helpers.buildRecentParams({ count: $("resourceCount").value || "20", sort: page.default_sort || "" }),
    ...parseJsonBox("resourceParams", {}),
  }
  if (patient && page.patient_param) params[page.patient_param] = patientParamValue(patient)
  return params
}

async function loadSelectedResource() {
  const page = state.selectedResourcePage
  if (!page) throw new Error("Wähle zuerst eine Resource-Seite.")
  const params = helpers.buildRecentParams({ count: $("resourceCount").value || "20", sort: page.default_sort || "" })
  await runResourceSearch(page.resource, params, `${page.resource} letzte 20`)
}

async function searchSelectedResource() {
  const page = state.selectedResourcePage
  if (!page) throw new Error("Wähle zuerst eine Resource-Seite.")
  const params = await selectedResourceParams()
  await runResourceSearch(page.resource, params, `${page.resource} Suche`)
}

async function readSelectedResource() {
  const page = state.selectedResourcePage
  const id = $("resourceReadId").value.trim()
  if (!page || !id) throw new Error("Resource und FHIR-ID angeben.")
  const result = await runFhir("GET", `${page.resource}/${id}`, {}, null, { label: `GET ${page.resource}/${id}` })
  const resource = firstResource(result)
  if (resource) openRow(helpers.rowFromResource(resource))
}

async function postSelectedResource() {
  const page = state.selectedResourcePage
  if (!page) throw new Error("Wähle zuerst eine Resource-Seite.")
  const resource = parseJsonBox("resourceCreate", genericTemplate())
  if (!resource?.resourceType) resource.resourceType = page.resource
  await runFhir("POST", page.resource, {}, resource, { label: `POST ${page.resource}` })
}

async function loadSettings() {
  const settings = await api("/api/settings", null, "GET")
  state.settings = settings
  $("tokenUrl").value = settings.token_url || ""
  $("baseUrl").value = settings.fhir_base_url || ""
  $("clientId").value = settings.client_id_effective || settings.client_id || ""
  $("scope").value = settings.default_scope || ""
  $("confirmationPhrase").placeholder = settings.write_confirmation_phrase || "LIVE"
  $("secretHint").textContent = settings.client_secret_available_from_env
    ? `Secret ist über ${settings.client_secret_env} verfügbar. Eingabe optional.`
    : `Secret fehlt noch. Eingabe hier oder Umgebungsvariable ${settings.client_secret_env}.`

  const preset = $("scopePreset")
  preset.innerHTML = ""
  for (const [key, value] of Object.entries(settings.resource_scope_presets || {})) {
    const option = document.createElement("option")
    option.value = value
    option.textContent = key
    preset.appendChild(option)
  }

  selectResourcePage("Patient")
}

function bind(id, event, handler) {
  $(id).addEventListener(event, (evt) => {
    Promise.resolve(handler(evt)).catch(showError)
  })
}

function initEvents() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((el) => el.classList.remove("active"))
      document.querySelectorAll(".tabpage").forEach((el) => el.classList.remove("active"))
      button.classList.add("active")
      document.getElementById(button.dataset.tab).classList.add("active")
    })
  })

  $("scopePreset").addEventListener("change", (event) => {
    if (event.target.value) $("scope").value = event.target.value
  })

  bind("useReadScopeBtn", "click", () => applyPageScope("read"))
  bind("useWriteScopeBtn", "click", () => applyPageScope("write"))

  bind("saveSettingsBtn", "click", async () => {
    const req = {
      token_url: $("tokenUrl").value.trim(),
      fhir_base_url: $("baseUrl").value.trim(),
      client_id: $("clientId").value.trim(),
      default_scope: scopeValue(),
    }
    showRequest({ settings_update: req, client_secret: "nicht gespeichert" })
    const result = await api("/api/settings", req)
    showResponse(result)
    await loadSettings()
  })

  bind("testTokenBtn", "click", async () => {
    const req = { scope: scopeValue(), client_secret: readSecret() }
    showRequest(req)
    try {
      const result = await api("/api/token/test", req)
      setTokenStatus(result)
      showResponse(result)
    } catch (err) {
      setTokenStatus({ ok: false, error: String(err.message || err) })
      throw err
    }
  })

  bind("metadataBtn", "click", () => runFhir("GET", "metadata", { _format: "json" }, null, { label: "Metadata", renderResults: false }))
  bind("providerBtn", "click", () => runFhir("GET", "Organization", { type: "prov", active: "true", _count: "10" }, null, { label: "Provider Organisationen" }))

  bind("loadRecentDocsBtn", "click", loadRecentDocuments)
  bind("searchDocsBtn", "click", searchDocuments)
  bind("resolveDocPatientBtn", "click", () => resolvePatient("docPatientIdentifier", "docPatientFhirId"))
  bind("docTypesBtn", "click", loadDocTypes)
  $("docTypeFilter").addEventListener("input", renderDocTypes)
  $("docTypesList").addEventListener("click", (event) => {
    const button = event.target.closest("[data-doc-type-code]")
    if (!button) return
    copyText(button.dataset.docTypeCode).catch(showError)
  })

  bind("docRefTemplateBtn", "click", () => {
    $("docRefCreate").value = pretty(docRefCreateTemplate())
  })
  bind("postDocRefBtn", "click", () => runFhir("POST", "DocumentReference", {}, parseJsonBox("docRefCreate"), { label: "POST DocumentReference" }))

  bind("loadRecentAppointmentsBtn", "click", loadRecentAppointments)
  bind("searchAppointmentsBtn", "click", searchAppointments)
  bind("resolveApptPatientBtn", "click", () => resolvePatient("apptPatientIdentifier", "apptPatientFhirId"))
  bind("apptTemplateBtn", "click", () => {
    $("apptCreate").value = pretty(appointmentTemplate())
  })
  bind("postApptBtn", "click", () => runFhir("POST", "Appointment", {}, parseJsonBox("apptCreate"), { label: "POST Appointment" }))

  $("resourceCards").addEventListener("click", (event) => {
    const button = event.target.closest("[data-resource-action]")
    if (!button) return
    const resource = button.dataset.resource
    selectResourcePage(resource)
    if (button.dataset.resourceAction === "readScope") applyPageScope("read")
    if (button.dataset.resourceAction === "load") loadSelectedResource().catch(showError)
  })
  bind("loadSelectedResourceBtn", "click", loadSelectedResource)
  bind("searchSelectedResourceBtn", "click", searchSelectedResource)
  bind("readSelectedResourceBtn", "click", readSelectedResource)
  bind("resolveResourcePatientBtn", "click", () => resolvePatient("resourcePatientIdentifier", "resourcePatientFhirId"))
  bind("resourceTemplateBtn", "click", () => {
    $("resourceCreate").value = pretty(genericTemplate())
  })
  bind("postSelectedResourceBtn", "click", postSelectedResource)

  bind("runExplorerBtn", "click", () => {
    const body = parseJsonBox("explorerBody", null)
    const params = parseJsonBox("explorerParams", {})
    return runFhir($("explorerMethod").value, $("explorerPath").value.trim(), params, body, { label: `${$("explorerMethod").value} ${$("explorerPath").value.trim()}` })
  })

  $("resultsBody").addEventListener("click", (event) => {
    const copyButton = event.target.closest("[data-copy-row]")
    if (copyButton) {
      const row = state.currentRows[Number(copyButton.dataset.copyRow)]
      copyText(row?.[copyButton.dataset.field]).catch(showError)
      event.stopPropagation()
      return
    }
    const openButton = event.target.closest("[data-open-row]")
    const rowElement = event.target.closest("[data-row-index]")
    const index = openButton ? Number(openButton.dataset.openRow) : Number(rowElement?.dataset.rowIndex)
    if (Number.isInteger(index) && state.currentRows[index]) openRow(state.currentRows[index])
  })

  $("historyBody").addEventListener("click", (event) => {
    const copyButton = event.target.closest("[data-history-copy]")
    if (copyButton) {
      const entry = state.history[Number(copyButton.dataset.historyCopy)]
      copyText(entry?.row?.[copyButton.dataset.field]).catch(showError)
      return
    }
    const openButton = event.target.closest("[data-history-open]")
    if (openButton) {
      const entry = state.history[Number(openButton.dataset.historyOpen)]
      if (entry?.row) openRow(entry.row)
    }
  })

  bind("clearResultsBtn", "click", () => {
    state.currentRows = []
    renderResults("Trefferliste geleert.")
  })
  bind("clearHistoryBtn", "click", () => {
    state.history = []
    renderHistory()
  })
  bind("copySelectedIdBtn", "click", () => copyText(state.selected?.fhirId || ""))
  bind("reloadSelectedBtn", "click", reloadSelected)
  bind("putSelectedBtn", "click", updateSelected)
  bind("deleteSelectedBtn", "click", deleteSelected)
}

async function main() {
  await loadSettings()
  initEvents()
  $("docRefCreate").value = pretty(docRefCreateTemplate())
  $("apptCreate").value = pretty(appointmentTemplate())
  renderResults()
  renderHistory()
  renderQuickEditor(null)
}

main().catch(showError)
