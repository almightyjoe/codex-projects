from __future__ import annotations

from pathlib import Path

from .models import CollectionResult


def render_friend_graph(result: CollectionResult) -> Path | None:
    if not result.friends:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import networkx as nx
    except Exception as exc:
        result.add_warning(f"Friend graph skipped; install networkx and matplotlib to enable it: {exc}")
        return None

    graph_dir = result.output_dir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    subject = result.profile.get("personaname") or result.profile.get("persona_name") or result.steamid64 or "Subject"
    graph = nx.Graph()
    graph.add_node(subject, kind="subject")
    for friend in result.friends[:150]:
        label = friend.get("name") or friend.get("steamid") or friend.get("url") or "Friend"
        graph.add_edge(subject, label)

    plt.figure(figsize=(11, 8))
    pos = nx.spring_layout(graph, seed=42, k=0.4)
    nx.draw_networkx_nodes(graph, pos, node_size=220, node_color="#2f81f7")
    nx.draw_networkx_edges(graph, pos, alpha=0.35)
    nx.draw_networkx_labels(graph, pos, font_size=7)
    plt.title(f"Visible Friend Graph ({len(result.friends)} friend nodes)")
    plt.axis("off")
    path = graph_dir / "friend_graph.png"
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()
    result.media["friend_graph"] = str(path)
    return path
