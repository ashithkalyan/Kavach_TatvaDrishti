"""
KAVACH Brain — Hidden Criminal Network Discovery Engine
============================================================
A heterogeneous, multi-entity graph — Person, Phone, Vehicle, Location
and Case nodes, connected by typed edges — plus classical graph
algorithms for discovery:

    Manja --used_phone--> Phone A --called--> Phone B --belongs_to--> Rakesh
                                                            |
                                                       owns_vehicle
                                                            v
                                                       KA05MJ4432 --seen_near--> Crime Scene

WHY CLASSICAL GRAPH ALGORITHMS, NOT A TRAINED GNN
A Graph Neural Network needs thousands of labeled "these two nodes ARE
/ ARE NOT connected" examples to learn embeddings worth trusting. We
don't have that — training one on synthetic hackathon data would mean
the model learns noise while looking sophisticated on a slide. Path-
finding, centrality, and community detection below are exact,
deterministic, and fully explainable — every hop in a discovered path
is a real row in a real table, not a learned weight nobody can
inspect. That directly satisfies the challenge brief's own Explainable
AI requirement, which a GNN's opaque embeddings would work against.
This module's job is architected so a genuine GNN could be dropped in
later as an additional signal, once real labeled data exists at scale
— it does not block that future.

Uses networkx — a standard, open-source, 100% local Python graph
library (same category as scikit-learn: a computational library, not
an external API or paid service).
"""
import networkx as nx


NODE_TYPES = {"person", "phone", "vehicle", "location", "case"}
EDGE_RELATIONSHIPS = {
    "used_phone", "called", "owns_vehicle", "seen_near",
    "involved_in_case", "occurred_at", "co_accused_with",
    "gang_member_with", "family_of",
}


def build_graph(nodes: list, edges: list) -> "nx.MultiDiGraph":
    """
    nodes: [{"id": str, "type": "person"|"phone"|"vehicle"|"location"|"case", "label": str, **attrs}]
    edges: [{"source": str, "target": str, "relationship": str, **attrs}]
    """
    G = nx.MultiDiGraph()
    for n in nodes:
        G.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    for e in edges:
        G.add_edge(e["source"], e["target"],
                    relationship=e.get("relationship", "linked_to"),
                    **{k: v for k, v in e.items() if k not in ("source", "target", "relationship")})
    return G


def find_hidden_paths(G: "nx.MultiDiGraph", source_id: str, target_id: str, max_hops: int = 4) -> list:
    """
    Multi-hop path discovery — the literal 'Manja -> Phone -> Phone ->
    Rakesh -> Vehicle -> Crime Scene' capability. Every returned path
    is a real, traceable chain of edges, not a similarity score.
    """
    if source_id not in G or target_id not in G:
        return []
    undirected = G.to_undirected()
    try:
        raw_paths = list(nx.all_simple_paths(undirected, source_id, target_id, cutoff=max_hops))
    except nx.NetworkXNoPath:
        return []
    described = [_describe_path(G, p) for p in raw_paths]
    described.sort(key=lambda p: p["hop_count"])
    return described[:10]


def _describe_path(G, path: list) -> dict:
    steps = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        rel = "linked_to"
        if G.has_edge(a, b):
            rel = list(G.get_edge_data(a, b).values())[0].get("relationship", "linked_to")
        elif G.has_edge(b, a):
            rel = list(G.get_edge_data(b, a).values())[0].get("relationship", "linked_to")
        steps.append({
            "from": a, "from_label": G.nodes[a].get("label", a), "from_type": G.nodes[a].get("type"),
            "to": b, "to_label": G.nodes[b].get("label", b), "to_type": G.nodes[b].get("type"),
            "relationship": rel,
        })
    return {"path": path, "steps": steps, "hop_count": len(path) - 1}


def compute_centrality(G: "nx.MultiDiGraph", node_type_filter: str = "person") -> list:
    """
    Who is the hub of the network — exact, classical, explainable.
    Betweenness centrality specifically surfaces 'brokers' — people who
    connect otherwise-separate clusters, often the most investigatively
    valuable finding in a criminal network.
    """
    simple = nx.DiGraph(G)
    degree = nx.degree_centrality(simple)
    try:
        betweenness = nx.betweenness_centrality(simple)
    except Exception:
        betweenness = {n: 0.0 for n in simple.nodes()}

    out = []
    for node, attrs in G.nodes(data=True):
        if node_type_filter and attrs.get("type") != node_type_filter:
            continue
        out.append({
            "id": node,
            "label": attrs.get("label", node),
            "degree_centrality": round(degree.get(node, 0), 3),
            "betweenness_centrality": round(betweenness.get(node, 0), 3),
            "role": "broker (connects separate clusters)" if betweenness.get(node, 0) > 0.15 else
                    "hub (many direct links)" if degree.get(node, 0) > 0.3 else "peripheral",
        })
    out.sort(key=lambda x: -(x["degree_centrality"] + x["betweenness_centrality"]))
    return out


def detect_communities(G: "nx.MultiDiGraph", node_type_filter: str = "person") -> list:
    """
    Classical community detection (greedy modularity) — surfaces likely
    gang/crew clusters the data was never explicitly labeled with,
    purely from connection density. This is how KAVACH can flag "this
    looks like an undocumented group" rather than only reporting gangs
    that were already tagged as such in the database.
    """
    undirected = G.to_undirected()
    if node_type_filter:
        keep = {n for n, d in G.nodes(data=True) if d.get("type") == node_type_filter}
        undirected = undirected.subgraph(keep).copy()
    if undirected.number_of_nodes() < 3 or undirected.number_of_edges() < 2:
        return []
    try:
        communities = nx.community.greedy_modularity_communities(undirected)
    except Exception:
        return []
    result = []
    for c in communities:
        if len(c) < 2:
            continue
        members = [{"id": n, "label": G.nodes[n].get("label", n)} for n in c]
        result.append({"size": len(c), "members": members})
    result.sort(key=lambda x: -x["size"])
    return result


def shared_attribute_links(records: list, id_field: str, attr_field: str) -> list:
    """
    Generic 'shared X' edge builder — e.g. two accused sharing a phone
    number, or two cases sharing a vehicle plate. Groups records by the
    attribute value and emits an edge between every pair that shares it.
    records: [{id_field: ..., attr_field: ...}, ...]
    """
    from collections import defaultdict
    groups = defaultdict(list)
    for r in records:
        val = r.get(attr_field)
        if val:
            groups[val].append(r[id_field])

    edges = []
    for val, ids in groups.items():
        ids = sorted(set(ids))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                edges.append({"source": ids[i], "target": ids[j],
                               "relationship": f"shared_{attr_field}", "shared_value": val})
    return edges
