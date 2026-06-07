"""
Canonical coverage graph normalization and similarity scoring.

States live on nodes (states[]), not as separate nodes. Relations use optional
from_state / to_state qualifiers. Both OPL reference and generated graphs pass
through the same canonicalize() pipeline before comparison.
"""
from __future__ import annotations

import copy
import re
from typing import Any

RELATION_ALIASES: dict[str, str] = {
    "procedurallink": "procedural_link",
    "agentlink": "agent_link",
    "instrumentlink": "instrument_link",
    "consumptionlink": "consumption_link",
    "resultlink": "result_link",
    "effectlink": "effect_link",
    "aggregationparticipation": "aggregation_participation",
    "exhibitioncharacterization": "exhibition_characterization",
    "generalizationspecialization": "generalization_specialization",
}

UNDIRECTED_RELATION_TYPES = frozenset({"aggregation_participation"})


def normalize_graph_key(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(name).lower().strip())


def normalize_relation_type(rel_type: str) -> str:
    key = normalize_graph_key(rel_type)
    return RELATION_ALIASES.get(key, key)


def _normalize_state_list(states: Any) -> list[str]:
    if not isinstance(states, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for state in states:
        key = normalize_graph_key(str(state))
        if key and key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def _collapse_state_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge legacy flat state nodes into parent states[] arrays."""
    if not nodes:
        return []

    working = copy.deepcopy(nodes)
    by_key: dict[str, dict[str, Any]] = {}
    for node in working:
        if not isinstance(node, dict):
            continue
        key = normalize_graph_key(node.get("name", ""))
        if key:
            by_key[key] = node

    absorbed: set[str] = set()
    for node in working:
        if not isinstance(node, dict):
            continue
        parent_key = normalize_graph_key(node.get("name", ""))
        if not parent_key:
            continue
        states = _normalize_state_list(node.get("states"))
        for relation in node.get("relations", []):
            if not isinstance(relation, dict):
                continue
            rel_type = normalize_relation_type(relation.get("type", ""))
            if rel_type != "exhibition_characterization":
                continue
            target_key = normalize_graph_key(relation.get("to", ""))
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
        key = normalize_graph_key(node.get("name", ""))
        if key in absorbed:
            continue
        result.append(node)
    return result


def _normalize_relation(
    relation: dict[str, Any],
    owner_key: str,
) -> dict[str, Any] | None:
    from_key = normalize_graph_key(relation.get("from", "")) or owner_key
    to_key = normalize_graph_key(relation.get("to", ""))
    rel_type = normalize_relation_type(relation.get("type", ""))
    from_state = normalize_graph_key(relation.get("from_state", "")) or None
    to_state = normalize_graph_key(relation.get("to_state", "")) or None

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
        name_key = normalize_graph_key(node.get("name", ""))
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


def graph_entities(graph: dict[str, Any]) -> dict[str, str]:
    entities: dict[str, str] = {}
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        name = node.get("name", "")
        if name:
            entities[name] = str(node.get("type", "object")).lower()
    return entities


def graph_states_by_entity(graph: dict[str, Any]) -> dict[str, set[str]]:
    states_map: dict[str, set[str]] = {}
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        name = node.get("name", "")
        if name:
            states_map[name] = set(_normalize_state_list(node.get("states")))
    return states_map


def _edge_key(
    from_node: str,
    from_state: str | None,
    to_node: str,
    to_state: str | None,
    rel_type: str,
) -> tuple[str, str | None, str, str | None, str] | tuple[str, str | None, str, str | None, str, bool]:
    if rel_type in UNDIRECTED_RELATION_TYPES:
        pair = tuple(sorted([from_node, to_node]))
        return (pair[0], from_state, pair[1], to_state, rel_type, True)
    return (from_node, from_state, to_node, to_state, rel_type)


def canonical_edges(graph: dict[str, Any]) -> set[tuple[Any, ...]]:
    edges: set[tuple[Any, ...]] = set()
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        owner = node.get("name", "")
        for relation in node.get("relations", []):
            if not isinstance(relation, dict):
                continue
            from_node = relation.get("from", owner)
            to_node = relation.get("to", "")
            rel_type = relation.get("type", "")
            if not from_node or not to_node or not rel_type:
                continue
            edges.add(
                _edge_key(
                    from_node,
                    relation.get("from_state"),
                    to_node,
                    relation.get("to_state"),
                    rel_type,
                )
            )
    return edges


def graph_similarity_score(
    reference_graph: dict[str, Any],
    generated_graph: dict[str, Any],
) -> dict[str, float]:
    ref = canonicalize_coverage_graph(reference_graph)
    gen = canonicalize_coverage_graph(generated_graph)

    ref_entities = graph_entities(ref)
    gen_entities = graph_entities(gen)
    ref_states = graph_states_by_entity(ref)
    gen_states = graph_states_by_entity(gen)
    ref_edges = canonical_edges(ref)
    gen_edges = canonical_edges(gen)

    if not gen_entities or not ref_entities:
        return {
            "entity_score": 0.0,
            "state_score": 0.0,
            "relation_score": 0.0,
            "overall_score": 0.0,
        }

    shared_entities = set(ref_entities.keys()) & set(gen_entities.keys())
    entity_score = len(shared_entities) / len(ref_entities)

    matched_states = 0
    total_states = 0
    for entity, ref_entity_states in ref_states.items():
        if entity not in gen_states:
            continue
        total_states += len(ref_entity_states)
        matched_states += len(ref_entity_states & gen_states[entity])
    state_score = matched_states / total_states if total_states else 1.0

    relation_score = (
        len(ref_edges & gen_edges) / len(ref_edges) if ref_edges else 1.0
    )

    overall = (entity_score + state_score + relation_score) / 3
    return {
        "entity_score": round(entity_score * 100, 2),
        "state_score": round(state_score * 100, 2),
        "relation_score": round(relation_score * 100, 2),
        "overall_score": round(overall * 100, 2),
    }
