"""
Canonical coverage graph normalization and similarity scoring.

States live on nodes (states[]), not as separate nodes. Relations use optional
from_state / to_state qualifiers. Both OPL reference and generated graphs pass
through the same canonicalize() pipeline before comparison.
"""

import copy
import re
from typing import Any

# Default graph coverage score
GRAPH_COVERAGE_SCORE_DEFAULT = {
    "entity_score": 0.0,
    "state_score": 0.0,
    "relation_score": 0.0,
    "overall_score": 0.0,
    "relation_matched": 0,
    "relation_applicable": 0,
    "relation_total": 0,
    "generated_relation_count": 0,
}

EDGE_SCHEMA = {
    "from": str,
    "from_state": str | None,
    "to": str,
    "to_state": str | None,
    "type": str,
    "undirected": False,
}

RELATION_ALIASES: dict[str, str] = {
    "procedurallink": "procedural_link",
    "procedural": "procedural_link",
    "link": "procedural_link",
    "agentlink": "agent_link",
    "agent": "agent_link",
    "instrumentlink": "instrument_link",
    "instrument": "instrument_link",
    "consumptionlink": "consumption_link",
    "consumption": "consumption_link",
    "resultlink": "result_link",
    "result": "result_link",
    "yields": "result_link",
    "effectlink": "effect_link",
    "effect": "effect_link",
    "changes": "effect_link",
    "aggregationparticipation": "aggregation_participation",
    "exhibitioncharacterization": "exhibition_characterization",
    "exhibition": "exhibition_characterization",
    "exhibits": "exhibition_characterization",
    "generalizationspecialization": "generalization_specialization",
}

RELATION_TYPE_COMPATIBLE: dict[str, set[str]] = {
    "agent_link": {"agent_link", "agent"},
    "instrument_link": {"instrument_link", "instrument"},
    "result_link": {"result_link", "result", "yields"},
    "effect_link": {"effect_link", "effect", "changes"},
    "procedural_link": {"procedural_link", "procedural", "link", "requires"},
    "consumption_link": {"consumption_link", "consumption"},
    "exhibition_characterization": {
        "exhibition_characterization",
        "exhibition",
        "exhibits",
    },
    "aggregation_participation": {"aggregation_participation", "aggregation"},
    "generalization_specialization": {
        "generalization_specialization",
        "generalization",
    },
}

def _is_edge_in(edge: dict[str, Any], check_edges: list[dict[str, Any]], check_states: dict[str, set[str]], allow_reverse: bool = True) -> bool:
    """
        Check if the edge is in the check_edges or check_states

        params:
            - edge : The edge to check
            - check_edges : The list of edges to check
            - check_states : The states to check
            - allow_reverse : Whether to allow reverse edges

        returns:
            - bool : True if the edge is in the check_edges or check_states, False otherwise
    """

    # --- _relation_satisfied_by_generated_states (inlined) ---
    if edge["type"] == "exhibition_characterization":
        target = edge["to"] or edge["from"]
        if target:
            entity_states = check_states.get(target, set())
            if edge["to_state"] and edge["to_state"] in entity_states:
                return True
            if edge["from_state"] and edge["from_state"] in entity_states:
                return True

    for check_edge in check_edges:
        # --- _same_relation_core (inlined) ---
        if edge["undirected"] != check_edge["undirected"]:
            continue

        # --- _relation_types_compatible (inlined) ---
        if edge["type"] != check_edge["type"]:
            types_ok = False
            for aliases in RELATION_TYPE_COMPATIBLE.values():
                if edge["type"] in aliases and check_edge["type"] in aliases:
                    types_ok = True
                    break
            if not types_ok:
                continue

        ref_from, ref_to = edge["from"], edge["to"]
        gen_from, gen_to = check_edge["from"], check_edge["to"]
        undirected = edge["undirected"]

        # --- _same_relation_endpoints (inlined) ---
        if undirected:
            endpoints_ok = tuple(sorted([ref_from, ref_to])) == tuple(
                sorted([gen_from, gen_to])
            )
        elif ref_from == gen_from and ref_to == gen_to:
            endpoints_ok = True
        else:
            endpoints_ok = (
                allow_reverse and ref_from == gen_to and ref_to == gen_from
            )

        if not endpoints_ok:
            continue

        # --- _relation_states_compatible (inlined) ---
        states_ok = True

        if edge["from_state"]:
            if check_edge["from_state"]:
                if edge["from_state"] != check_edge["from_state"]:
                    states_ok = False
            elif edge["from_state"] not in check_states.get(edge["from"], set()):
                states_ok = False

        if states_ok and edge["to_state"]:
            if check_edge["to_state"]:
                if edge["to_state"] != check_edge["to_state"]:
                    states_ok = False
            elif edge["to_state"] not in check_states.get(edge["to"], set()):
                states_ok = False

        if states_ok:
            return True

    return False

def _normalize_graph_key(name: str) -> str:
    """
        Normalize a graph key for comparison

        params:
            - name : The name to normalize

        returns:
            - str : The normalized graph key
    """
    return re.sub(r"[\s_\-]+", "", str(name).lower().strip())

def _normalize_state_list(states: Any) -> list[str]:
    """
        Normalize a list of states

        params:
            - states : The list of states to normalize

        returns:
            - list[str] : The normalized list of states
    """
    # Check if the states is a list
    if not isinstance(states, list):
        return []

    normalized: set[str] = set()
    for state in states:
        # Normalize the state and add to the set
        key = _normalize_graph_key(str(state))
        if key and key not in normalized:
            normalized.add(key)
    
    return list(normalized)

def canonicalize_coverage_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Normalize a coverage graph into a comparable canonical form."""
    if not isinstance(graph, dict):
        return {"nodes": []}

    raw_nodes = graph.get("nodes", [])
    if not isinstance(raw_nodes, list):
        return {"nodes": []}

    collapsed = _collapse_state_nodes(
        [n for n in raw_nodes if isinstance(n, dict)]
    )

    canonical_nodes: list[dict[str, Any]] = []
    for node in collapsed:
        name_key = _normalize_graph_key(node.get("name", ""))
        if not name_key:
            continue

        node_type = str(node.get("type", "")).lower().strip()
        if node_type not in {"object", "process"}:
            node_type = "object"

        relations: list[dict[str, Any]] = []
        seen_relations: set[tuple[Any, ...]] = set()
        for relation in node.get("relations", []):
            if not isinstance(relation, dict):
                continue
            normalized = _normalize_relation(relation, name_key)
            if normalized is None:
                continue
            rel_key = (
                normalized["from"],
                normalized.get("from_state"),
                normalized["to"],
                normalized.get("to_state"),
                normalized["type"],
            )
            if rel_key in seen_relations:
                continue
            seen_relations.add(rel_key)
            relations.append(normalized)

        canonical_nodes.append(
            {
                "name": name_key,
                "type": node_type,
                "states": _normalize_state_list(node.get("states")),
                "relations": relations,
            }
        )

    return {"nodes": canonical_nodes}

def _extract_graph_params(graph: dict[str, Any]) -> tuple:
    """
        Extract from given graph the entities, states and edges

        params:
            - graph : The graph to extract the entities, states and edges from

        returns:
            - tuple : (entities, states_map, edges)
    """

    entities: dict[str, str] = {}
    states_map: dict[str, list[str]] = {}
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[Any, ...]] = set()

    for node in graph.get("nodes", []):
        # Check if the node is a dictionary with a name
        if not isinstance(node, dict) or not node.get("name", ""):
            continue

        # Add name to entities and states_map
        name = node.get("name", "")
        entities[name] = str(node.get("type", "object")).lower()
        states_map[name] = _normalize_state_list(node.get("states"))

        # Extract edges from the node
        for relation in node.get("relations", []):
            # Check if the relation is a dictionary
            if not isinstance(relation, dict):
                continue

            # Check if the relation has a from and to node and type
            from_node = relation.get("from", name)
            to_node = relation.get("to", "")
            rel_type = relation.get("type", "")
            if not from_node or not to_node or not rel_type:
                continue

            # Create the edge
            edge = EDGE_SCHEMA.copy()
            edge["from"] = from_node
            edge["from_state"] = relation.get("from_state")
            edge["to"] = to_node
            edge["to_state"] = relation.get("to_state")
            edge["type"] = rel_type

            # Check if the relation is an aggregation participation
            if rel_type == "aggregation_participation":
                sorted_edge = sorted([from_node, to_node])
                edge["from"] = sorted_edge[0]
                edge["to"] = sorted_edge[1]
                edge["undirected"] = True


            edge_key = (
                edge["from"],
                edge.get("from_state"),
                edge["to"],
                edge.get("to_state"),
                edge["type"],
                edge.get("undirected", False),
            )
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            edges.append(edge)

    return entities, states_map, edges

def graph_similarity_score(reference_graph: dict, generated_graph: dict) -> dict:
    """
        Calculate the graph similarity score between the reference and generated graphs
        
        params:
            - reference_graph : The reference graph
            - generated_graph : The generated graph

        returns:
            - dict : The graph similarity score
    """
    scores = GRAPH_COVERAGE_SCORE_DEFAULT.copy()

    # Check if the reference and generated graphs are defined
    if not reference_graph or not generated_graph:
        return scores

    # Extract the entities, states and edges from the reference and generated graphs
    ref_entities, ref_states, ref_edges = _extract_graph_params(reference_graph)
    gen_entities, gen_states, gen_edges = _extract_graph_params(generated_graph)

    # Check if the entities are defined
    if not gen_entities or not ref_entities:
        return scores

    # Use only edges between entities present in both graphs
    shared_edges = []
    shared_entities = set(ref_entities.keys()) & set(gen_entities.keys())
    for ref_edge in ref_edges:
        if ref_edge["from"] in shared_entities and ref_edge["to"] in shared_entities:
            shared_edges.append(ref_edge)

    # Calculate the entity score (name + type must match; missing entities penalized)
    matched_entities = sum(
        1
        for entity in ref_entities
        if entity in gen_entities and ref_entities[entity] == gen_entities[entity]
    )
    entity_score = matched_entities / len(ref_entities)

    gen_states_sets = {name: set(states) for name, states in gen_states.items()}

    # Calculate the state score
    total_states = sum(len(ref_states[e]) for e in ref_entities)
    matched_states = sum(
        len(set(ref_states[e]) & gen_states_sets.get(e, set()))
        for e in ref_entities
        if e in gen_states_sets
    )
    state_score = matched_states / total_states if total_states else 1.0

    # Calculate the relation score
    matched_relations = 0
    relation_score = 0.0
    if shared_edges:
        for ref_edge in shared_edges:
            if _is_edge_in(ref_edge, gen_edges, gen_states_sets):
                matched_relations += 1
        relation_score = matched_relations / len(shared_edges)
    elif ref_edges:
        relation_score = 0.0
    else:
        relation_score = 1.0

    # Calculate the overall score
    overall = (entity_score + state_score + relation_score) / 3

    # Update the scores
    scores["entity_score"] = round(entity_score * 100, 2)
    scores["state_score"] = round(state_score * 100, 2)
    scores["relation_score"] = round(relation_score * 100, 2)
    scores["overall_score"] = round(overall * 100, 2)
    scores["relation_matched"] = matched_relations if shared_edges else 0
    scores["relation_applicable"] = len(shared_edges)
    scores["relation_total"] = len(ref_edges)
    scores["generated_relation_count"] = len(gen_edges)
    return scores

def normalize_relation_type(rel_type: str) -> str:
    key = _normalize_graph_key(rel_type)
    return RELATION_ALIASES.get(key, key)

def _collapse_state_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge legacy flat state nodes into parent states[] arrays."""
    if not nodes:
        return []

    working = copy.deepcopy(nodes)
    by_key: dict[str, dict[str, Any]] = {}
    for node in working:
        if not isinstance(node, dict):
            continue
        key = _normalize_graph_key(node.get("name", ""))
        if key:
            by_key[key] = node

    absorbed: set[str] = set()
    for node in working:
        if not isinstance(node, dict):
            continue
        parent_key = _normalize_graph_key(node.get("name", ""))
        if not parent_key:
            continue
        states = _normalize_state_list(node.get("states"))
        for relation in node.get("relations", []):
            if not isinstance(relation, dict):
                continue
            rel_type = normalize_relation_type(relation.get("type", ""))
            if rel_type != "exhibition_characterization":
                continue
            target_key = _normalize_graph_key(relation.get("to", ""))
            if not target_key or target_key == parent_key:
                continue
            if target_key in by_key and target_key not in states:
                states.append(target_key)
                absorbed.add(target_key)
        node["states"] = states

    result: list[dict[str, Any]] = []
    for node in working:
        if not isinstance(node, dict):
            continue
        key = _normalize_graph_key(node.get("name", ""))
        if key in absorbed:
            continue
        result.append(node)
    return result

def _normalize_relation(
    relation: dict[str, Any],
    owner_key: str,
) -> dict[str, Any] | None:
    from_key = _normalize_graph_key(relation.get("from", "")) or owner_key
    to_key = _normalize_graph_key(relation.get("to", ""))
    rel_type = normalize_relation_type(relation.get("type", ""))
    from_state = _normalize_graph_key(relation.get("from_state", "")) or None
    to_state = _normalize_graph_key(relation.get("to_state", "")) or None

    if not to_key:
        return None

    if rel_type == "exhibition_characterization":
        if to_key != from_key and not to_state:
            to_state = to_key
            to_key = from_key

    return {
        "from": from_key,
        "to": to_key,
        "type": rel_type,
        "from_state": from_state,
        "to_state": to_state,
    }

def coerce_coverage_graph(payload: Any) -> dict[str, Any] | None:
    """Normalize common Gemini JSON shapes into ``{"nodes": [...]}``."""
    if isinstance(payload, list):
        if payload and all(isinstance(node, dict) for node in payload):
            return {"nodes": payload}
        return None

    if not isinstance(payload, dict):
        return None

    for key, value in payload.items():
        if key.lower() == "nodes" and isinstance(value, list):
            return {"nodes": value}

    for key in (
        "coverage_graph",
        "code_coverage_graph",
        "graph",
        "opl_coverage_graph",
        "opl_graph",
    ):
        nested = payload.get(key)
        if isinstance(nested, dict):
            coerced = coerce_coverage_graph(nested)
            if coerced is not None:
                return coerced

    nodes: list[dict[str, Any]] = []
    for key, node_type in (("objects", "object"), ("processes", "process")):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                node = dict(item)
                node.setdefault("type", node_type)
                node.setdefault("states", [])
                node.setdefault("relations", [])
                nodes.append(node)
            elif isinstance(item, str) and item.strip():
                nodes.append(
                    {
                        "name": item.strip(),
                        "type": node_type,
                        "states": [],
                        "relations": [],
                    }
                )

    if nodes:
        return {"nodes": nodes}

    return None
