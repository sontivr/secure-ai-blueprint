"""
CI/CD deployment flow diagram.
Run from the repo root: python3 docs/diagrams/source/gen_cicd_flow.py
"""
from diagrams import Diagram, Cluster, Edge
from diagrams.k8s.compute import Pod, Deployment
from diagrams.k8s.infra import Master
from diagrams.onprem.container import Docker
from diagrams.onprem.ci import GithubActions
from diagrams.onprem.vcs import Github
from diagrams.programming.language import Python

OUT = "docs/diagrams/exported/k3s-cicd-deployment-flow"

graph_attr = {
    "fontsize": "20",
    "fontname": "Helvetica Bold",
    "bgcolor": "white",
    "pad": "1.2",
    "splines": "spline",
    "nodesep": "0.9",
    "ranksep": "1.2",
}

cluster_attr = {
    "fontsize": "13",
    "fontname": "Helvetica",
    "style": "rounded",
    "bgcolor": "#f7f9fc",
}

with Diagram(
    "Secure AI Homelab — CI/CD Deployment Flow",
    filename=OUT,
    outformat="png",
    show=False,
    direction="LR",
    graph_attr=graph_attr,
):
    with Cluster("GitHub", graph_attr=cluster_attr):
        repo = Github("secure-ai-blueprint\ngit push → main")

    with Cluster("Job 1 · Lint & Test  (self-hosted runner)", graph_attr={**cluster_attr, "bgcolor": "#e8f5e9"}):
        lint = GithubActions("ruff check\nbackend/")
        test = Python("pytest\nbackend/tests/  (90 tests)")

    with Cluster("Job 2 · Build & Deploy  (self-hosted runner)", graph_attr={**cluster_attr, "bgcolor": "#eef2ff"}):
        build = Docker("docker build\nsecure-ai-backend:$SHA")
        save = Docker("docker save\n→ .tar")
        transfer = GithubActions("multipass transfer\n→ controlplane")

    with Cluster("k3s Cluster", graph_attr={**cluster_attr, "bgcolor": "#fff8e1"}):
        cp = Master("controlplane\ncontainerd import")
        deploy = Deployment("kubectl apply\ndeployment.yaml")
        pod = Pod("secure-ai-backend\nnew pod rolling out")

    # Pipeline flow
    repo >> Edge(label="triggers") >> lint
    lint >> test
    test >> Edge(label="passed", color="#2ecc71") >> build
    build >> save >> transfer
    transfer >> cp
    cp >> Edge(label="image available") >> deploy
    deploy >> Edge(label="rollout restart", color="#6c63ff") >> pod
