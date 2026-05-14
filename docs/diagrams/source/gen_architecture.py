"""
Architecture overview diagram.
Run from the repo root: python3 docs/diagrams/source/gen_architecture.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.k8s.compute import Pod
from diagrams.k8s.network import Service
from diagrams.k8s.storage import PVC, PV
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.network import Traefik, Internet
from diagrams.onprem.monitoring import Grafana, Prometheus
from diagrams.onprem.database import Qdrant

OUT = "docs/diagrams/exported/k3s-homelab-architecture"

graph_attr = {
    "fontsize": "20",
    "fontname": "Helvetica Bold",
    "bgcolor": "white",
    "pad": "1.2",
    "splines": "spline",
    "nodesep": "1.0",
    "ranksep": "1.4",
    "rankdir": "LR",
}

cluster_attr = {
    "fontsize": "13",
    "fontname": "Helvetica",
    "style": "rounded",
    "bgcolor": "#f7f9fc",
}

with Diagram(
    "Secure AI Homelab — Architecture",
    filename=OUT,
    outformat="png",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    # ── Left: clients & CI/CD ─────────────────────────────────────────────────
    with Cluster("External", graph_attr=cluster_attr):
        browser = Internet("Browser / curl\nsecure-ai.lab")
        runner = GithubActions("GH Actions\nSelf-hosted Runner")

    # ── Right: k3s cluster ────────────────────────────────────────────────────
    with Cluster("Kubernetes Cluster  ·  k3s on Multipass VMs", graph_attr={**cluster_attr, "bgcolor": "#eef2ff"}):

        with Cluster("Ingress & Networking", graph_attr=cluster_attr):
            mlb = Service("MetalLB\n192.168.2.240")
            traefik = Traefik("Traefik Ingress\nHTTPS · cert-manager")

        with Cluster("Application", graph_attr={**cluster_attr, "bgcolor": "#e8f5e9"}):
            backend = Pod("secure-ai-backend\nFastAPI · JWT · RBAC · Rate-limit")

        with Cluster("AI Layer", graph_attr=cluster_attr):
            chroma = Qdrant("ChromaDB\nVector Store")
            ollama = Pod("Ollama\nllama3")

        with Cluster("Persistent Storage", graph_attr=cluster_attr):
            pvc = PVC("backend-pvc")
            pv = PV("Longhorn PV")

        with Cluster("Observability", graph_attr={**cluster_attr, "bgcolor": "#fff8e1"}):
            prom = Prometheus("Prometheus\n+ Alertmanager")
            graf = Grafana("Grafana\ngrafana.lab")

    # ── Connections ────────────────────────────────────────────────────────────
    # HTTPS traffic path
    browser >> Edge(label="HTTPS") >> mlb >> traefik >> backend

    # CI/CD deploy path
    runner >> Edge(label="containerd import\n+ kubectl apply", style="dashed", color="#6c63ff") >> backend

    # RAG pipeline
    backend >> chroma >> pvc >> pv
    backend >> ollama

    # Observability
    backend >> Edge(label="metrics", style="dashed", color="#f59e0b") >> prom
    prom >> graf
