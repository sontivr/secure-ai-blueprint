"""
Runtime request flow diagram.
Run from the repo root: python3 docs/diagrams/source/gen_runtime_flow.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.k8s.compute import Pod
from diagrams.k8s.network import Ingress, Service
from diagrams.k8s.storage import PVC, PV
from diagrams.onprem.network import Traefik, Internet
from diagrams.onprem.monitoring import Grafana, Prometheus
from diagrams.onprem.database import Qdrant
from diagrams.programming.language import Python

OUT = "docs/diagrams/exported/k3s-runtime-request-flow"

graph_attr = {
    "fontsize": "20",
    "fontname": "Helvetica Bold",
    "bgcolor": "white",
    "pad": "1.2",
    "splines": "spline",
    "nodesep": "0.8",
    "ranksep": "1.2",
}

cluster_attr = {
    "fontsize": "13",
    "fontname": "Helvetica",
    "style": "rounded",
    "bgcolor": "#f7f9fc",
}

with Diagram(
    "Secure AI Homelab — Runtime Request Flow",
    filename=OUT,
    outformat="png",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    with Cluster("Client", graph_attr=cluster_attr):
        browser = Internet("Browser / curl\nsecure-ai.lab")

    with Cluster("Entry Point  ·  TLS via cert-manager", graph_attr={**cluster_attr, "bgcolor": "#fff0f0"}):
        mlb = Service("MetalLB\n192.168.2.240")
        traefik = Traefik("Traefik Ingress\nHTTPS termination")

    with Cluster("RAG Pipeline", graph_attr={**cluster_attr, "bgcolor": "#e8f5e9"}):
        backend = Pod("secure-ai-backend\nFastAPI · JWT auth · Rate limit")

        with Cluster("Vector Retrieval", graph_attr=cluster_attr):
            chroma = Qdrant("ChromaDB\n/app/data/chroma")
            pvc = PVC("backend-pvc")
            pv = PV("Longhorn PV")

        ollama = Pod("Ollama\nllama3  (LLM inference)")

    with Cluster("Observability", graph_attr={**cluster_attr, "bgcolor": "#fff8e1"}):
        prom = Prometheus("Prometheus\n+ node exporters")
        graf = Grafana("Grafana\ngrafana.lab")

    # Primary API path
    browser >> Edge(label="HTTPS POST /query") >> mlb >> traefik
    traefik >> Edge(label="route: secure-ai.lab") >> backend

    # RAG internals
    backend >> Edge(label="embed + search") >> chroma
    chroma >> pvc >> pv
    backend >> Edge(label="LLM prompt") >> ollama
    ollama >> Edge(label="answer", color="#2ecc71") >> backend
    backend >> Edge(label="JSON response", color="#2ecc71") >> browser

    # Observability
    backend >> Edge(label="metrics :8000/metrics", style="dashed", color="#f59e0b") >> prom
    prom >> graf
