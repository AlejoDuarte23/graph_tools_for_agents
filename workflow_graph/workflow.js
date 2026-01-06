export class WorkflowGraph {
  constructor({ stage, edgesSvg, nodesHost, logEl }) {
    this.stage = stage;
    this.edgesSvg = edgesSvg;
    this.nodesHost = nodesHost;
    this.logEl = logEl;

    const rootStyle = getComputedStyle(document.documentElement);
    this.NODE_W = parseFloat(rootStyle.getPropertyValue("--node-w"));
    this.NODE_H = parseFloat(rootStyle.getPropertyValue("--node-h"));
    this.GAP_X  = parseFloat(rootStyle.getPropertyValue("--gap-x"));
    this.GAP_Y  = parseFloat(rootStyle.getPropertyValue("--gap-y"));
    this.EDGE_W = (rootStyle.getPropertyValue("--edge-w") || "8").trim();

    this.typeStyles = {
      geometry:       { bg: "#5aa9ff", glyph: "□" },
      seismic:        { bg: "#ffb36b", glyph: "∿" },
      wind:           { bg: "#6fd3a0", glyph: "≋" },
      structural:     { bg: "#ff6f6f", glyph: "△" },
      footing_cap:    { bg: "#b58bff", glyph: "▭" },
      footing_design: { bg: "#ffd86b", glyph: "○" },
      default:        { bg: "#d5d5d5", glyph: "•" },
    };

    this.data = { nodes: [] };
    this.byId = new Map();
    this.edges = [];          // {from,to}
    this.positions = new Map();// id -> {x,y}
    this.dragged = new Set();
    this.activeId = null;
    this.running = false;
  }

  nodeCount() { return (this.data.nodes || []).length; }
  edgeCount() { return this.edges.length; }

  log(msg) {
    if (!this.logEl) return;
    this.logEl.textContent += msg + "\n";
    this.logEl.scrollTop = this.logEl.scrollHeight;
  }

  clearLog() {
    if (this.logEl) this.logEl.textContent = "";
  }

  setData(workflow) {
    this.data = workflow && typeof workflow === "object" ? workflow : { nodes: [] };
    this._validateAndBuildGraph();
  }

  _validateAndBuildGraph() {
    const nodes = Array.isArray(this.data.nodes) ? this.data.nodes : [];
    this.byId.clear();
    this.edges = [];

    for (const n of nodes) {
      if (!n || typeof n.id !== "string" || !n.id.trim()) {
        throw new Error("Each node must have a non-empty string id.");
      }
      if (this.byId.has(n.id)) {
        throw new Error("Duplicate node id: " + n.id);
      }
      this.byId.set(n.id, n);
    }

    for (const n of nodes) {
      const deps = Array.isArray(n.depends_on) ? n.depends_on : [];
      for (const dep of deps) {
        const depId = dep && typeof dep.node_id === "string" ? dep.node_id : null;
        if (!depId || !this.byId.has(depId)) {
          throw new Error(`Node "${n.id}" depends_on unknown node "${depId}".`);
        }
        this.edges.push({ from: depId, to: n.id });
      }
    }
  }

  topoSort() {
    const nodes = Array.isArray(this.data.nodes) ? this.data.nodes : [];
    const indeg = new Map();
    const out = new Map();

    for (const n of nodes) {
      indeg.set(n.id, 0);
      out.set(n.id, []);
    }
    for (const e of this.edges) {
      indeg.set(e.to, (indeg.get(e.to) || 0) + 1);
      out.get(e.from).push(e.to);
    }

    const q = [];
    for (const [id, d] of indeg.entries()) {
      if (d === 0) q.push(id);
    }

    const order = [];
    while (q.length) {
      const id = q.shift();
      order.push(id);
      for (const nxt of out.get(id)) {
        indeg.set(nxt, indeg.get(nxt) - 1);
        if (indeg.get(nxt) === 0) q.push(nxt);
      }
    }

    if (order.length !== nodes.length) return { ok: false, order: [] };
    return { ok: true, order };
  }

  _computeDepths(order) {
    const depth = new Map();
    for (const id of order) depth.set(id, 0);

    for (const id of order) {
      const node = this.byId.get(id);
      const deps = Array.isArray(node.depends_on) ? node.depends_on : [];
      let d = 0;
      for (const dep of deps) {
        d = Math.max(d, (depth.get(dep.node_id) || 0) + 1);
      }
      depth.set(id, d);
    }
    return depth;
  }

  relayout({ resetDragged }) {
    if (resetDragged) this.dragged.clear();

    const res = this.topoSort();
    if (!res.ok) {
      this.log("ERROR: cycle detected; layout based on dependencies is not possible.");
      return;
    }

    const order = res.order;
    const depth = this._computeDepths(order);

    const layers = new Map();
    let maxDepth = 0;
    for (const id of order) {
      const d = depth.get(id) || 0;
      maxDepth = Math.max(maxDepth, d);
      if (!layers.has(d)) layers.set(d, []);
      layers.get(d).push(id);
    }

    const w = this.stage.clientWidth;
    const topPad = 60;
    const leftPad = 40;

    if (resetDragged) this.positions.clear();

    for (let d = 0; d <= maxDepth; d++) {
      const ids = layers.get(d) || [];
      const count = ids.length;
      if (count === 0) continue;

      const totalW = (count * this.NODE_W) + ((count - 1) * this.GAP_X);
      const startX = Math.max(leftPad, (w - totalW) / 2);

      for (let i = 0; i < count; i++) {
        const id = ids[i];
        if (!resetDragged && this.dragged.has(id)) continue;
        const x = startX + i * (this.NODE_W + this.GAP_X);
        const y = topPad + d * (this.NODE_H + this.GAP_Y);
        this.positions.set(id, { x, y });
      }
    }

    this._ensurePositionsForMissing();
  }

  _ensurePositionsForMissing() {
    const nodes = Array.isArray(this.data.nodes) ? this.data.nodes : [];
    const missing = [];
    for (const n of nodes) {
      if (!this.positions.has(n.id)) missing.push(n.id);
    }
    if (!missing.length) return;

    const w = this.stage.clientWidth;
    const startX = 40;
    const y = 40;
    let x = startX;

    for (const id of missing) {
      if (x + this.NODE_W > w - 40) x = startX;
      this.positions.set(id, { x, y });
      x += this.NODE_W + 20;
    }
  }

  render() {
    this._renderNodes();
    this._drawEdges();
  }

  _renderNodes() {
    this.nodesHost.innerHTML = "";
    const nodes = Array.isArray(this.data.nodes) ? this.data.nodes : [];

    for (const n of nodes) {
      const pos = this.positions.get(n.id);
      if (!pos) continue;

      const style = this.typeStyles[n.type] || this.typeStyles.default;

      const el = document.createElement("div");
      el.className = "node";
      el.dataset.id = n.id;
      el.style.left = pos.x + "px";
      el.style.top = pos.y + "px";
      el.innerHTML = `
        <div class="icon" style="background:${style.bg};">${style.glyph}</div>
        <div class="title" title="${escapeHtml(n.title || n.id)}">${escapeHtml(n.title || n.id)}</div>
      `;

      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this.setActive(n.id);
      });

      this._attachDrag(el, n.id);
      this.nodesHost.appendChild(el);
    }
  }

  setActive(idOrNull) {
    this.activeId = idOrNull;
    for (const el of this.nodesHost.querySelectorAll(".node")) {
      el.classList.toggle("active", idOrNull && el.dataset.id === idOrNull);
    }
  }

  _attachDrag(el, id) {
    let startX = 0, startY = 0, originX = 0, originY = 0;
    let dragging = false;

    el.addEventListener("pointerdown", (ev) => {
      ev.preventDefault();
      el.setPointerCapture(ev.pointerId);
      const p = this.positions.get(id);
      if (!p) return;

      dragging = true;
      this.dragged.add(id);

      startX = ev.clientX;
      startY = ev.clientY;
      originX = p.x;
      originY = p.y;
    });

    el.addEventListener("pointermove", (ev) => {
      if (!dragging) return;
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;

      const x = originX + dx;
      const y = originY + dy;
      this.positions.set(id, { x, y });
      el.style.left = x + "px";
      el.style.top = y + "px";
      this._drawEdges();
    });

    const end = (ev) => {
      if (!dragging) return;
      dragging = false;
      try { el.releasePointerCapture(ev.pointerId); } catch {}
    };

    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
  }

  _setSvgSize() {
    this.edgesSvg.setAttribute("width", this.stage.clientWidth);
    this.edgesSvg.setAttribute("height", this.stage.clientHeight);
    this.edgesSvg.setAttribute("viewBox", `0 0 ${this.stage.clientWidth} ${this.stage.clientHeight}`);
  }

  _drawEdges() {
    this._setSvgSize();
    this.edgesSvg.innerHTML = "";

    const mk = (tag) => document.createElementNS("http://www.w3.org/2000/svg", tag);

    for (const e of this.edges) {
      const p1 = this.positions.get(e.from);
      const p2 = this.positions.get(e.to);
      if (!p1 || !p2) continue;

      const x1 = p1.x + this.NODE_W / 2;
      const y1 = p1.y + this.NODE_H;
      const x2 = p2.x + this.NODE_W / 2;
      const y2 = p2.y;

      const c1x = x1;
      const c1y = y1 + 80;
      const c2x = x2;
      const c2y = y2 - 80;

      const path = mk("path");
      path.setAttribute("d", `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`);
      path.setAttribute("fill", "none");
      path.setAttribute("stroke", "#111");
      path.setAttribute("stroke-width", this.EDGE_W);
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("stroke-linejoin", "round");
      this.edgesSvg.appendChild(path);

      const s = mk("circle");
      s.setAttribute("cx", x1);
      s.setAttribute("cy", y1);
      s.setAttribute("r", "8");
      s.setAttribute("fill", "#f7f7f7");
      s.setAttribute("stroke", "#111");
      s.setAttribute("stroke-width", "4");
      this.edgesSvg.appendChild(s);

      const t = mk("circle");
      t.setAttribute("cx", x2);
      t.setAttribute("cy", y2);
      t.setAttribute("r", "8");
      t.setAttribute("fill", "#111");
      this.edgesSvg.appendChild(t);
    }
  }

  async run() {
    if (this.running) return;
    this.running = true;
    this.clearLog();

    const res = this.topoSort();
    if (!res.ok) {
      this.log("ERROR: cycle detected. Cannot run a cyclic workflow.");
      this.running = false;
      return;
    }

    const order = res.order;
    this.log("Run order:");
    this.log("  " + order.join(" -> "));
    this.log("");

    const stepMs = 650;
    for (const id of order) {
      this.setActive(id);
      this.log("Running: " + id);
      await sleep(stepMs);
    }

    this.setActive(null);
    this.log("\nDone.");
    this.running = false;
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}