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

UNDIRECTED_RELATION_TYPES = frozenset({"aggregation_participation"})


def normalize_graph_key(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(name).lower().strip())


def normalize_relation_type(rel_type: str) -> str:
    key = normalize_graph_key(rel_type)
    return RELATION_ALIASES.get(key, key)


def _relation_types_compatible(left_type: str, right_type: str) -> bool:
    if left_type == right_type:
        return True
    for aliases in RELATION_TYPE_COMPATIBLE.values():
        if left_type in aliases and right_type in aliases:
            return True
    return False


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


def _split_opl_entity_list(text: str) -> list[str]:
    text = re.sub(r"\s+and\s+", ", ", text.strip())
    return [part.strip() for part in text.split(",") if part.strip()]


def _add_graph_relation(
    nodes_by_key: dict[str, dict[str, Any]],
    owner_name: str,
    to_name: str,
    rel_type: str,
    *,
    from_state: str | None = None,
    to_state: str | None = None,
) -> None:
    owner_key = normalize_graph_key(owner_name)
    owner = nodes_by_key.get(owner_key)
    if owner is None:
        return
    relation = {
        "from": owner_name.strip(),
        "to": to_name.strip(),
        "type": rel_type,
    }
    if from_state:
        relation["from_state"] = from_state.strip()
    if to_state:
        relation["to_state"] = to_state.strip()
    owner.setdefault("relations", []).append(relation)


def build_reference_graph_from_opl(opl: str) -> dict[str, Any]:
    """
    Build a coverage graph directly from OPL text when Gemini extraction fails.
    Parses common Object-Process Language sentence patterns deterministically.
    """
    nodes_by_key: dict[str, dict[str, Any]] = {}

    def ensure_node(name: str, node_type: str = "object") -> dict[str, Any]:
        clean_name = name.strip()
        key = normalize_graph_key(clean_name)
        if key not in nodes_by_key:
            nodes_by_key[key] = {
                "name": clean_name,
                "type": node_type,
                "states": [],
                "relations": [],
            }
        return nodes_by_key[key]

    def add_states(entity_name: str, states_text: str) -> None:
        node = ensure_node(entity_name)
        for state in _split_opl_entity_list(states_text.replace(" or ", ", ")):
            normalized = normalize_graph_key(state)
            if normalized and normalized not in {
                normalize_graph_key(existing) for existing in node["states"]
            }:
                node["states"].append(state.strip())

    lines = [re.sub(r"^\d+\.\s*", "", line).strip() for line in opl.splitlines()]
    lines = [line for line in lines if line]

    for line in lines:
        consists_match = re.match(r"^(.+?) consists of (.+?)\.?$", line, re.IGNORECASE)
        if consists_match:
            for entity in _split_opl_entity_list(consists_match.group(2)):
                ensure_node(entity, "object")
            continue

        process_match = re.match(r"^(.+?) is a process\.?$", line, re.IGNORECASE)
        if process_match:
            ensure_node(process_match.group(1), "process")
            continue

        exhibits_match = re.match(r"^(.+?) exhibits (.+?)\.?$", line, re.IGNORECASE)
        if exhibits_match:
            ensure_node(exhibits_match.group(1), "object")
            add_states(exhibits_match.group(1), exhibits_match.group(2))
            continue

        can_be_match = re.match(r"^(.+?) can be (.+?)\.?$", line, re.IGNORECASE)
        if can_be_match:
            ensure_node(can_be_match.group(1), "object")
            add_states(can_be_match.group(1), can_be_match.group(2))
            continue

        agent_match = re.match(r"^(.+?) is the agent of (.+?)\.?$", line, re.IGNORECASE)
        if agent_match:
            agent, process = agent_match.group(1), agent_match.group(2)
            ensure_node(agent, "object")
            ensure_node(process, "process")
            _add_graph_relation(nodes_by_key, process, agent, "agent_link")
            continue

        instrument_match = re.match(
            r"^(.+?) is the instrument of (.+?)\.?$", line, re.IGNORECASE
        )
        if instrument_match:
            instrument, process = instrument_match.group(1), instrument_match.group(2)
            ensure_node(instrument, "object")
            ensure_node(process, "process")
            _add_graph_relation(nodes_by_key, process, instrument, "instrument_link")
            continue

        yields_match = re.match(r"^(.+?) yields (.+?)\.?$", line, re.IGNORECASE)
        if yields_match:
            process, result = yields_match.group(1), yields_match.group(2)
            ensure_node(process, "process")
            ensure_node(result, "object")
            _add_graph_relation(nodes_by_key, process, result, "result_link")
            continue

        changes_match = re.match(
            r"^(.+?) changes (.+?) from (.+?) to (.+?)(?:\s+when\b.*)?\.?$",
            line,
            re.IGNORECASE,
        )
        if changes_match:
            process, target, from_state, to_state = changes_match.groups()
            ensure_node(process, "process")
            ensure_node(target, "object")
            add_states(target, f"{from_state}, {to_state}")
            _add_graph_relation(
                nodes_by_key,
                process,
                target,
                "effect_link",
                from_state=from_state,
                to_state=to_state,
            )
            continue

        requires_match = re.match(r"^(.+?) requires (.+?) to be (.+?)\.?$", line, re.IGNORECASE)
        if requires_match:
            process, target, state = requires_match.groups()
            ensure_node(process, "process")
            ensure_node(target, "object")
            add_states(target, state)
            _add_graph_relation(
                nodes_by_key,
                process,
                target,
                "procedural_link",
                to_state=state,
            )

    return {"nodes": list(nodes_by_key.values())}


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


def _unpack_edge(
    edge: tuple[Any, ...],
) -> tuple[str, str | None, str, str | None, str, bool]:
    if len(edge) == 6:
        from_node, from_state, to_node, to_state, rel_type, undirected = edge
        return from_node, from_state, to_node, to_state, rel_type, bool(undirected)
    from_node, from_state, to_node, to_state, rel_type = edge
    return from_node, from_state, to_node, to_state, rel_type, False


def _same_relation_endpoints(
    ref_from: str,
    ref_to: str,
    gen_from: str,
    gen_to: str,
    *,
    undirected: bool,
    allow_reverse: bool,
) -> bool:
    if undirected:
        return tuple(sorted([ref_from, ref_to])) == tuple(sorted([gen_from, gen_to]))
    if ref_from == gen_from and ref_to == gen_to:
        return True
    return allow_reverse and ref_from == gen_to and ref_to == gen_from


def _same_relation_core(
    ref_edge: tuple[Any, ...],
    gen_edge: tuple[Any, ...],
    *,
    allow_reverse: bool = True,
) -> bool:
    ref_from, _, ref_to, _, ref_type, ref_undirected = _unpack_edge(ref_edge)
    gen_from, _, gen_to, _, gen_type, gen_undirected = _unpack_edge(gen_edge)
    if ref_undirected != gen_undirected:
        return False
    if not _relation_types_compatible(ref_type, gen_type):
        return False
    return _same_relation_endpoints(
        ref_from,
        ref_to,
        gen_from,
        gen_to,
        undirected=ref_undirected,
        allow_reverse=allow_reverse,
    )


def _relation_states_compatible(
    ref_edge: tuple[Any, ...],
    gen_edge: tuple[Any, ...],
    gen_states: dict[str, set[str]],
) -> bool:
    ref_from, ref_from_state, ref_to, ref_to_state, _, _ = _unpack_edge(ref_edge)
    _, gen_from_state, _, gen_to_state, _, _ = _unpack_edge(gen_edge)

    if ref_from_state:
        if gen_from_state:
            if ref_from_state != gen_from_state:
                return False
        elif ref_from_state not in gen_states.get(ref_from, set()):
            return False

    if ref_to_state:
        if gen_to_state:
            if ref_to_state != gen_to_state:
                return False
        elif ref_to_state not in gen_states.get(ref_to, set()):
            return False

    return True


def _relation_satisfied_by_generated_states(
    ref_edge: tuple[Any, ...],
    gen_states: dict[str, set[str]],
) -> bool:
    """Treat states[] coverage as satisfying exhibition/state qualifier relations."""
    ref_from, ref_from_state, ref_to, ref_to_state, rel_type, _ = _unpack_edge(ref_edge)
    if rel_type != "exhibition_characterization":
        return False
    target = ref_to or ref_from
    if not target:
        return False
    entity_states = gen_states.get(target, set())
    if ref_to_state and ref_to_state in entity_states:
        return True
    if ref_from_state and ref_from_state in entity_states:
        return True
    return False


def _applicable_reference_edges(
    ref_edges: set[tuple[Any, ...]],
    shared_entities: set[str],
) -> list[tuple[Any, ...]]:
    """Only score relations between entities present in both graphs."""
    applicable: list[tuple[Any, ...]] = []
    for ref_edge in ref_edges:
        ref_from, _, ref_to, _, _, _ = _unpack_edge(ref_edge)
        if ref_from in shared_entities and ref_to in shared_entities:
            applicable.append(ref_edge)
    return applicable


def _relation_edge_matched(
    ref_edge: tuple[Any, ...],
    gen_edges: set[tuple[Any, ...]],
    gen_states: dict[str, set[str]],
) -> bool:
    if _relation_satisfied_by_generated_states(ref_edge, gen_states):
        return True
    for gen_edge in gen_edges:
        if _same_relation_core(ref_edge, gen_edge) and _relation_states_compatible(
            ref_edge, gen_edge, gen_states
        ):
            return True
    return False


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

    applicable_ref_edges = _applicable_reference_edges(ref_edges, shared_entities)
    matched_relations = 0
    if applicable_ref_edges:
        matched_relations = sum(
            1
            for ref_edge in applicable_ref_edges
            if _relation_edge_matched(ref_edge, gen_edges, gen_states)
        )
        relation_score = matched_relations / len(applicable_ref_edges)
    elif ref_edges:
        relation_score = 0.0
    else:
        relation_score = 1.0

    overall = (entity_score + state_score + relation_score) / 3
    return {
        "entity_score": round(entity_score * 100, 2),
        "state_score": round(state_score * 100, 2),
        "relation_score": round(relation_score * 100, 2),
        "overall_score": round(overall * 100, 2),
        "relation_matched": matched_relations if applicable_ref_edges else 0,
        "relation_applicable": len(applicable_ref_edges),
        "relation_total": len(ref_edges),
        "generated_relation_count": len(gen_edges),
    }
