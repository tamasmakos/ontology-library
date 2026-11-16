const LIST_CAP = 80;
const NEIGHBOR_CAP = 24;
const TYPE_LABEL = {
  class: "Classes",
  property: "Properties",
  individual: "Individuals",
  datatype: "Datatypes",
};
const OPEN_ON = {
  foaf: "http://xmlns.com/foaf/0.1/Person",
  bfo: "http://purl.obolibrary.org/obo/BFO_0000001",
  "owl-time": "http://www.w3.org/2006/time#TemporalEntity",
  schemaorg: "https://schema.org/Person",
  skos: "http://www.w3.org/2004/02/skos/core#Concept",
  wine: "http://www.w3.org/TR/2003/PR-owl-guide-20031209/wine#Wine",
  food: "http://www.w3.org/TR/2003/PR-owl-guide-20031209/food#EdibleThing",
};

const state = {
  catalog: null,
  graph: null,
  record: null,
  filter: "class",
  query: "",
  selected: null,
};

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  if (page === "index") loadIndex();
  if (page === "ontology") loadOntology();
});

async function loadIndex() {
  const main = document.getElementById("catalog");
  try {
    state.catalog = await loadData("catalog.json", "ONTOLOGY_CATALOG");
  } catch (error) {
    main.textContent = `The catalog could not be loaded. ${error.message}`;
    return;
  }
  const list = document.createElement("ol");
  list.className = "catalog";
  for (const row of state.catalog.ontologies) {
    list.append(catalogItem(row));
  }
  main.replaceChildren(list);
}

function catalogItem(row) {
  const item = document.createElement("li");
  const heading = document.createElement("h2");
  const link = document.createElement("a");
  link.href = `ontology.html?id=${encodeURIComponent(row.id)}`;
  link.textContent = row.name;
  heading.append(link);
  const summary = document.createElement("p");
  summary.textContent = row.summary;
  const counts = document.createElement("p");
  counts.className = "counts";
  counts.textContent = `${row.nodes.toLocaleString()} nodes · ${row.edges.toLocaleString()} edges · ${row.counts.class.toLocaleString()} classes · ${row.counts.property.toLocaleString()} properties · ${row.counts.individual.toLocaleString()} individuals`;
  const license = document.createElement("p");
  license.className = "counts";
  license.append(`${formatName(row.format)} · `);
  license.append(externalLink(row.license_url, row.license));
  item.append(heading, summary, counts, license);
  return item;
}

async function loadOntology() {
  const params = new URLSearchParams(location.search);
  const id = params.get("id");
  const title = document.getElementById("title");
  if (!id) {
    title.textContent = "Missing ontology";
    return;
  }
  try {
    state.catalog = await loadData("catalog.json", "ONTOLOGY_CATALOG");
    state.record = state.catalog.ontologies.find((row) => row.id === id);
    if (!state.record) throw new Error(`No ontology named ${id}.`);
    title.textContent = state.record.name;
    document.title = state.record.name;
    document.getElementById("summary").textContent = state.record.summary;
    renderMeta(state.record);
    state.graph = await loadData(`graphs/${encodeURIComponent(id)}.json`, "ONTOLOGY_GRAPH");
  } catch (error) {
    title.textContent = "Could not open this ontology";
    document.getElementById("summary").textContent = error.message;
    return;
  }
  state.byId = new Map(state.graph.nodes.map((node) => [node.id, node]));
  const requested = params.get("node");
  const opening = state.byId.has(requested) ? requested : OPEN_ON[id];
  const node = state.byId.get(opening) || firstOfType("class") || state.graph.nodes[0];
  if (node) {
    state.filter = node.types.includes("class") ? "class" : node.types[0];
    state.selected = node.id;
  }
  document.getElementById("q").addEventListener("input", (event) => {
    state.query = event.target.value.trim();
    renderResults();
  });
  renderFilters();
  renderResults();
  renderDetail();
  revealSelected();
}

function renderMeta(row) {
  const meta = document.getElementById("meta");
  meta.replaceChildren();
  meta.append(
    `${row.nodes.toLocaleString()} nodes · ${row.edges.toLocaleString()} edges · ${formatName(row.format)} · `,
  );
  meta.append(externalLink(row.license_url, row.license));
  if (row.homepage) {
    meta.append(" · ");
    meta.append(externalLink(row.homepage, "Homepage"));
  }
  if (row.nodes > 500) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = "This ontology is large. Search the list, then read the selected term and its neighbors.";
    meta.insertAdjacentElement("afterend", note);
  }
}

function renderFilters() {
  const bar = document.getElementById("filters");
  bar.replaceChildren();
  const kinds = ["class", "property", "individual"];
  if (state.record.counts.datatype) kinds.push("datatype");
  for (const kind of kinds) {
    const count = state.record.counts[kind];
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${TYPE_LABEL[kind]} ${count.toLocaleString()}`;
    button.setAttribute("aria-pressed", String(state.filter === kind));
    button.addEventListener("click", () => {
      state.filter = kind;
      renderFilters();
      renderResults();
    });
    bar.append(button);
  }
}

function renderResults() {
  const matches = matchingNodes();
  let shown = matches.slice(0, LIST_CAP);
  const current = matches.find((node) => node.id === state.selected);
  if (current && !shown.includes(current)) shown = [current, ...shown.slice(0, LIST_CAP - 1)];
  const count = document.getElementById("match-count");
  const noun = countNoun(state.filter, matches.length);
  if (!matches.length) {
    count.textContent = state.query
      ? `No ${noun} match “${state.query}”.`
      : `No ${noun} in this ontology.`;
  } else if (matches.length > shown.length) {
    count.textContent = `Showing ${shown.length} of ${matches.length.toLocaleString()} ${noun}. Search to narrow the list.`;
  } else {
    count.textContent = `${matches.length.toLocaleString()} ${noun}.`;
  }
  const list = document.getElementById("results");
  list.replaceChildren();
  for (const node of shown) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.append(kindMark(node), document.createTextNode(node.label || node.id));
    button.setAttribute("aria-pressed", String(node.id === state.selected));
    button.addEventListener("click", () => select(node.id));
    item.append(button);
    list.append(item);
  }
}

function renderDetail() {
  const panel = document.getElementById("detail");
  const node = state.byId.get(state.selected);
  if (!node) {
    panel.textContent = "Select a term.";
    return;
  }
  panel.replaceChildren();
  const heading = document.createElement("h2");
  heading.textContent = node.label || node.id;
  const types = document.createElement("p");
  types.className = "hint";
  types.textContent = node.types.join(", ");
  const description = document.createElement("p");
  description.textContent = node.description || "No description in this graph.";
  const iriLabel = document.createElement("h3");
  iriLabel.textContent = "IRI";
  const iri = document.createElement("p");
  iri.className = "iri";
  if (/^https?:\/\//.test(node.iri)) {
    iri.append(externalLink(node.iri, node.iri));
  } else {
    iri.textContent = node.iri;
  }
  const neighborLabel = document.createElement("h3");
  const groups = neighborGroups(node.id);
  const total = groups.reduce((sum, group) => sum + group.edges.length, 0);
  neighborLabel.textContent = total === 1 ? "1 neighbor" : `${total.toLocaleString()} neighbors`;
  panel.append(heading, types, description, iriLabel, iri, neighborLabel);
  if (!groups.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "Nothing in this graph links to this term.";
    panel.append(empty);
    return;
  }
  for (const group of groups) {
    const title = document.createElement("h3");
    const extra = group.edges.length > NEIGHBOR_CAP ? ` (showing ${NEIGHBOR_CAP} of ${group.edges.length})` : "";
    title.textContent = `${group.name}${extra}`;
    const list = document.createElement("ul");
    list.className = "neighbors";
    for (const edge of group.edges.slice(0, NEIGHBOR_CAP)) {
      const otherId = edge.source === node.id ? edge.target : edge.source;
      const other = state.byId.get(otherId);
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = other ? (other.label || other.id) : otherId;
      button.addEventListener("click", () => select(otherId));
      item.append(button);
      list.append(item);
    }
    panel.append(title, list);
  }
}

function select(id) {
  if (!state.byId.has(id)) return;
  state.selected = id;
  const node = state.byId.get(id);
  if (!node.types.includes(state.filter)) {
    state.filter = node.types[0];
    state.query = "";
    document.getElementById("q").value = "";
    renderFilters();
  }
  const params = new URLSearchParams(location.search);
  params.set("node", id);
  history.replaceState(null, "", `?${params.toString()}`);
  renderResults();
  renderDetail();
  revealSelected();
}

function matchingNodes() {
  const query = state.query.toLowerCase();
  return state.graph.nodes
    .filter((node) => node.types.includes(state.filter))
    .filter((node) => {
      if (!query) return true;
      const label = (node.label || "").toLowerCase();
      const iri = node.iri.toLowerCase();
      return label.includes(query) || iri.includes(query);
    })
    .sort((a, b) => (a.label || a.id).localeCompare(b.label || b.id, undefined, { sensitivity: "base" }));
}

function neighborGroups(nodeId) {
  const buckets = new Map();
  for (const edge of state.graph.edges) {
    if (edge.source !== nodeId && edge.target !== nodeId) continue;
    const name = relationName(edge, nodeId);
    if (!buckets.has(name)) buckets.set(name, []);
    buckets.get(name).push(edge);
  }
  return [...buckets.entries()]
    .map(([name, edges]) => ({
      name,
      edges: edges.sort((a, b) => otherLabel(a, nodeId).localeCompare(otherLabel(b, nodeId), undefined, { sensitivity: "base" })),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function relationName(edge, nodeId) {
  const outgoing = edge.source === nodeId;
  const label = edge.label || "linked";
  if (label === "specializes") return outgoing ? "specializes" : "specialized by";
  if (label === "domain") return outgoing ? "has domain" : "domain of";
  if (label === "range") return outgoing ? "has range" : "range of";
  if (label === "type") return outgoing ? "instance of" : "has instance";
  return outgoing ? `related by ${label}` : `incoming ${label}`;
}

function otherLabel(edge, nodeId) {
  const otherId = edge.source === nodeId ? edge.target : edge.source;
  const other = state.byId.get(otherId);
  return other ? (other.label || other.id) : otherId;
}

function firstOfType(kind) {
  return state.graph.nodes
    .filter((node) => node.types.includes(kind))
    .sort((a, b) => (a.label || a.id).localeCompare(b.label || b.id, undefined, { sensitivity: "base" }))[0];
}

function revealSelected() {
  const pressed = document.querySelector('#results button[aria-pressed="true"]');
  const list = document.getElementById("results");
  if (!pressed || !list) return;
  const listRect = list.getBoundingClientRect();
  const buttonRect = pressed.getBoundingClientRect();
  if (buttonRect.top < listRect.top || buttonRect.bottom > listRect.bottom) {
    list.scrollTop += buttonRect.top - listRect.top - 8;
  }
}

function kindMark(node) {
  const mark = document.createElement("span");
  mark.className = "kind";
  mark.textContent = node.types[0];
  return mark;
}

function externalLink(href, text) {
  const link = document.createElement("a");
  link.href = href;
  link.textContent = text;
  link.rel = "noreferrer";
  link.target = "_blank";
  return link;
}

function countNoun(kind, count) {
  const singular = { class: "class", property: "property", individual: "individual", datatype: "datatype" }[kind];
  if (count === 1) return singular;
  if (singular.endsWith("y")) return `${singular.slice(0, -1)}ies`;
  return `${singular}s`;
}

function formatName(format) {
  if (format === "rdfxml") return "RDF/XML";
  if (format === "turtle") return "Turtle";
  if (format === "jsonld") return "JSON-LD";
  return format;
}

async function loadData(jsonPath, globalName) {
  if (jsonPath.startsWith("/")) throw new Error(`Root-absolute path ${jsonPath}`);
  if (location.protocol !== "file:") {
    const response = await fetch(jsonPath);
    if (!response.ok) throw new Error(`${jsonPath} returned ${response.status}.`);
    return response.json();
  }
  const scriptPath = jsonPath.replace(/\.json$/, ".js");
  await loadScript(scriptPath);
  const data = globalThis[globalName];
  if (!data) throw new Error(`${scriptPath} did not load.`);
  return data;
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Could not load ${src}`));
    document.head.append(script);
  });
}
