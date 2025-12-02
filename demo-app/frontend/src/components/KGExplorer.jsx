import React, { useEffect, useRef, useState } from "react";
import NeoVis, { NEOVIS_ADVANCED_CONFIG } from "neovis.js/dist/neovis.js";

const KGExplorer = () => {
  const containerRef = useRef(null);
  const vizRef = useRef(null);
  const [terms, setTerms] = useState([]);
  const [newTerm, setNewTerm] = useState("");
  const [selectedNode, setSelectedNode] = useState(null);
  const [relatedNodes, setRelatedNodes] = useState([]);

  const buildQuery = (termList) => {
    const cleaned = termList
      .map((t) => (t || "").trim())
      .filter((t) => t.length > 0);

    if (cleaned.length === 0) {
      return {
        cypher: "MATCH (n)-[r]-(m) WITH DISTINCT n,r,m RETURN n,r,m LIMIT 25",
      };
    }

    const clauses = cleaned.map(
      (t) =>
        `toLower(coalesce(n.name, n.summary, n.type, "")) CONTAINS toLower("${t.replace(/"/g, '\"')}")`
    );
    const whereClause = clauses.join(" AND ");
    const cypher = `
      MATCH (n:Entity)-[r]-(m)
      WHERE ${whereClause}
      WITH DISTINCT n,r,m
      RETURN n,r,m
      LIMIT 50
    `;
    return { cypher };
  };

  const renderGraph = (termList = terms) => {
    if (!containerRef.current) return;
    if (vizRef.current) {
      try {
        vizRef.current.clearNetwork();
      } catch (e) {}
    }

    const url = import.meta.env.VITE_NEO4J_URI || "bolt://localhost:7687";
    const user = import.meta.env.VITE_NEO4J_USER || "neo4j";
    const password = import.meta.env.VITE_NEO4J_PASSWORD || "password";

    const { cypher } = buildQuery(termList);
    if (!cypher || cypher.trim().length === 0) return;

    const config = {
      containerId: "neo4j-vis",
      neo4j: {
        serverUrl: url,
        serverUser: user,
        serverPassword: password,
      },
      visConfig: {
        nodes: {
          shape: "dot",
        },
        edges: {
          arrows: { to: { enabled: true } },
        },
      },
      labels: {
        Person: {
          label: "name",
          caption: "name",
        },
        Organization: {
          label: "name",
          caption: "name",
        },
        Entity: {
          label: "name",
          caption: "name",
          [NEOVIS_ADVANCED_CONFIG]: {
            function: {
              title: (node) =>
                node.properties?.name
                  ? `${node.properties.name} (${node.properties.type || "Entity"})`
                  : "Entity",
            },
          },
        },
        NewsItem: {
          caption: "",
          [NEOVIS_ADVANCED_CONFIG]: {
            function: {
              title: (node) => node.properties?.summary?.slice(0, 120) || "NewsItem",
            },
          },
        },
        Event: {
          label: "type",
          caption: "type",
        },
      },
      relationships: {
        KNOWS: {},
        RELATED: { caption: true },
        MENTIONED_IN: { caption: true },
        PARTICIPATES_IN: { caption: true },
        REPORTED_IN: { caption: true },
      },
      initialCypher: cypher,
      parameters: {},
    };

    const viz = new NeoVis(config);

    viz.registerOnEvent("clickNode", (e) => {
      const node = e?.node;
      if (!node) {
        setSelectedNode(null);
        setRelatedNodes([]);
        return;
      }
      const nodesDs = viz._data?.nodes;
      const edgesDs = viz._data?.edges;
      const clicked = nodesDs?.get(node.id) || node;

      const rawProps =
        node.raw?.properties || clicked.raw?.properties || clicked.properties || {};
      const selected = {
        ...clicked,
        properties: rawProps,
        label: clicked.label || clicked.group || "Node",
      };

      if (!edgesDs) {
        setSelectedNode(selected);
        setRelatedNodes([]);
        return;
      }

      const connectedEdges = edgesDs.get({
        filter: (edge) => edge.from === node.id || edge.to === node.id,
      });
      const neighborIds = new Set();
      connectedEdges.forEach((edge) => {
        if (edge.from !== node.id) neighborIds.add(edge.from);
        if (edge.to !== node.id) neighborIds.add(edge.to);
      });
      const neighbors = Array.from(neighborIds)
        .map((id) => nodesDs.get(id))
        .filter(Boolean);

      setSelectedNode(selected);
      setRelatedNodes(neighbors);
    });

    viz.render();
    vizRef.current = viz;
  };

  useEffect(() => {
    renderGraph([]);
    return () => {
      if (vizRef.current) {
        try {
          vizRef.current.clearNetwork();
        } catch (e) {}
      }
    };
  }, []);

  const handleAddTerm = (e) => {
    e.preventDefault();
    const t = (newTerm || "").trim();
    if (!t) return;
    if (terms.includes(t)) return;
    const updated = [...terms, t];
    setTerms(updated);
    setNewTerm("");
    renderGraph(updated);
  };

  const handleClearTerms = () => {
    setTerms([]);
    setSelectedNode(null);
    setRelatedNodes([]);
    renderGraph([]);
  };

  return (
    <div className="h-full w-full bg-gray-900 text-white p-4 overflow-hidden flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">Knowledge Graph Explorer</h2>
        <form onSubmit={handleAddTerm} className="flex gap-2 items-center">
          <input
            value={newTerm}
            onChange={(e) => setNewTerm(e.target.value)}
            placeholder="Add keyword"
            className="px-3 py-2 rounded bg-gray-800 border border-gray-700 text-sm w-64"
          />
          <button
            type="submit"
            className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 rounded text-sm font-semibold"
          >
            Add term
          </button>
          <button
            type="button"
            onClick={handleClearTerms}
            className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm border border-gray-700"
          >
            Clear
          </button>
        </form>
        <div className="flex gap-2 items-center">
          {terms.map((t) => (
            <span
              key={t}
              className="px-2 py-1 text-xs bg-indigo-700 rounded border border-indigo-500"
            >
              {t}
            </span>
          ))}
        </div>
      </div>
      <div className="flex-1 min-h-0 grid grid-cols-3 gap-3">
        <div
          id="neo4j-vis"
          ref={containerRef}
          className="col-span-2 rounded-lg border border-gray-800 overflow-hidden bg-gray-800"
        />
        <div className="rounded-lg border border-gray-800 bg-gray-850 p-3 overflow-auto">
          <h3 className="text-sm font-semibold mb-2">Selection</h3>
          {!selectedNode && (
            <div className="text-gray-400 text-sm">Click a node to view details.</div>
          )}
          {selectedNode && (
            <div className="space-y-2 text-sm">
              <div>
                <div className="text-gray-400">ID</div>
                <div className="font-semibold">{selectedNode.id}</div>
              </div>
              <div>
                <div className="text-gray-400">Label</div>
                <div className="font-semibold">{selectedNode.label || selectedNode.group || "Node"}</div>
              </div>
              <div>
                <div className="text-gray-400">Caption</div>
                <div className="font-semibold">
                  {selectedNode.title || selectedNode.caption || selectedNode.properties?.name || "N/A"}
                </div>
              </div>
              <div>
                <div className="text-gray-400">Properties</div>
                <pre className="bg-gray-900 rounded p-2 text-xs text-gray-300 whitespace-pre-wrap break-words">
                  {JSON.stringify(selectedNode.properties || {}, null, 2)}
                </pre>
              </div>
              <div>
                <div className="text-gray-400 mb-1">Related Nodes</div>
                <div className="space-y-1">
                  {relatedNodes.length === 0 && (
                    <div className="text-gray-500 text-xs">None</div>
                  )}
                  {relatedNodes.map((n) => (
                    <div
                      key={n.id}
                      className="p-2 rounded bg-gray-900 border border-gray-800 text-xs"
                    >
                      <div className="font-semibold">{n.properties?.name || n.label || n.id}</div>
                      <div className="text-gray-400">
                        {n.properties?.type || n.group || "Node"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default KGExplorer;
