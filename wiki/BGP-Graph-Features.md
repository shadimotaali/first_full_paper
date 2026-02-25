# BGP Graph Feature Extraction

This page documents every feature extracted by the [`bgp_graph_features.ipynb`](../scripts/bgp_graph_features.ipynb) pipeline. The pipeline processes BGP RIB snapshots to construct AS-level topology graphs and computes **16 graph-level** and **10 node-level** features per snapshot.

> **Scope:** All features are computed on the **largest connected component (LCC)** of the ego subgraph (k-hop neighborhood of a target AS). Graph-level features describe the local topology; node-level features are computed for every AS in the LCC.

---

## Table of Contents

- [Graph-Level Features (16)](#graph-level-features-16)
  - [1 - Assortativity](#1---assortativity)
  - [2 - Density](#2---density)
  - [3 - Clustering Coefficient](#3---clustering-coefficient-global-and-average-local)
  - [4 - Diameter and Average Path Length](#4---diameter-and-average-path-length)
  - [5 - Algebraic Connectivity](#5---algebraic-connectivity-fiedler-value)
  - [6 - Spectral Radius](#6---spectral-radius)
  - [7 - Percolation Limit](#7---percolation-limit)
  - [8 - Symmetry Ratio](#8---symmetry-ratio)
  - [9 - Natural Connectivity](#9---natural-connectivity)
  - [10 - Kirchhoff Index](#10---kirchhoff-index)
  - [11 - Log Spanning Trees](#11---log-number-of-spanning-trees)
  - [12 - Edge and Node Connectivity](#12---edge-and-node-connectivity)
  - [13 - Rich-Club Coefficient](#13---rich-club-coefficient)
  - [14 - Betweenness Centrality Distribution](#14---betweenness-centrality-distribution)
  - [15 - k-Core Decomposition Metrics](#15---k-core-decomposition-metrics)
  - [16 - Spectral Gap](#16---spectral-gap-and-eigenvalue-ratio)
- [Node-Level Features (10)](#node-level-features-10)
  - [1 - Degree Centrality](#1---degree-centrality)
  - [2 - Betweenness Centrality](#2---betweenness-centrality)
  - [3 - Closeness Centrality](#3---closeness-centrality)
  - [4 - Eigenvector Centrality](#4---eigenvector-centrality)
  - [5 - PageRank](#5---pagerank)
  - [6 - Local Clustering Coefficient](#6---local-clustering-coefficient)
  - [7 - Average Neighbor Degree](#7---average-neighbor-degree)
  - [8 - Node Clique Number](#8---node-clique-number)
  - [9 - Eccentricity](#9---eccentricity)
  - [10 - Core Number (k-Shell)](#10---core-number-k-shell)
- [Quick Reference Tables](#quick-reference-tables)
- [Implementation Notes](#implementation-notes)

---

## Graph-Level Features (16)

These features are extracted by `extract_graph_level_features()` (Cell 14). The function takes the LCC as a NetworkX graph (with an optional NetworKit copy for performance) and returns a dictionary of feature values plus `shared_data` that is reused by node-level extraction.

### 1 - Assortativity

| | |
|---|---|
| **Column** | `assortativity` |
| **Type** | float in [-1, 1] |
| **Formula** | Pearson correlation of degrees at the two endpoints of every edge |
| **Interpretation** | Positive values (assortative): high-degree nodes preferentially connect to other high-degree nodes. Negative values (disassortative): hubs connect to low-degree nodes. The Internet AS topology is famously disassortative — large transit providers connect to many small stub ASes. |
| **Anomaly signal** | A sudden shift toward 0 may indicate a major transit provider going down. A shift toward -1 could signal a route leak flooding connections across hierarchy tiers. |
| **Code** | `nx.degree_assortativity_coefficient(G_lcc)` |
| **Citation** | Newman, "Assortative mixing in networks," *Phys. Rev. Lett.* 89, 208701 (2002) |

---

### 2 - Density

| | |
|---|---|
| **Column** | `density` |
| **Type** | float in [0, 1] |
| **Formula** | ρ = 2\|E\| / (\|V\|(\|V\|-1)) |
| **Interpretation** | Fraction of possible edges that actually exist. The AS-level Internet is extremely sparse (density ~10⁻⁴ to 10⁻⁵). |
| **Anomaly signal** | A noticeable change indicates many new peering relationships appearing (e.g., IXP adding members) or many links disappearing (large-scale outage). |
| **Code** | `nx.density(G_lcc)` |
| **Citation** | Standard graph theory definition |

---

### 3 - Clustering Coefficient (Global and Average Local)

| | |
|---|---|
| **Columns** | `clustering_global`, `clustering_avg_local` |
| **Type** | float in [0, 1] |
| **Formula** | Global (transitivity): C_global = 3 × triangles / connected triples |
| | Average local: C_avg = (1/n) Σ C(v), where C(v) = 2·tri(v) / (deg(v)(deg(v)-1)) |
| **Interpretation** | Tendency of neighbors to also be neighbors of each other. High clustering reflects dense peering clusters (IXP meshes). Low clustering characterizes hierarchical transit relationships. |
| **Anomaly signal** | A sudden drop could indicate a peering fabric disruption (IXP failure). An increase might signal new dense peering arrangements or artificial route injection. |
| **Code** | NetworKit `ClusteringCoefficient.exactGlobal()` / `sequentialAvgLocal()`, or NetworkX `transitivity()` / `average_clustering()` as fallback |
| **Citation** | Watts & Strogatz, "Collective dynamics of 'small-world' networks," *Nature* 393 (1998) |

---

### 4 - Diameter and Average Path Length

| | |
|---|---|
| **Columns** | `diameter`, `diameter_approximate` (bool), `avg_path_length` |
| **Type** | int (diameter), float (avg path length) |
| **Formula** | Diameter: D = max d(u,v) over all pairs |
| | Average path length: L = (1/(n(n-1))) Σ d(u,v) |
| **Interpretation** | Worst-case and typical number of AS hops between any two ASes. The AS Internet has small-world properties: diameter ~10-15, average path length ~3-4, despite 70k+ nodes. |
| **Anomaly signal** | An increase suggests the network is becoming less well-connected (loss of critical transit links). A decrease could indicate new shortcut peering links. |
| **Code** | NetworKit `Diameter(algo=AUTOMATIC)` or NetworkX `diameter()`. For large graphs (n ≥ 20,000), average path length is estimated from 500 BFS samples. |
| **Citation** | Watts & Strogatz, *Nature* 393 (1998) |

---

### 5 - Algebraic Connectivity (Fiedler Value)

| | |
|---|---|
| **Column** | `algebraic_connectivity` |
| **Type** | float ≥ 0 |
| **Formula** | μ₂(L) — the second-smallest eigenvalue of the graph Laplacian L = D - A |
| **Interpretation** | How well-connected the graph is. A larger Fiedler value means the graph is harder to disconnect. It equals 0 if and only if the graph is disconnected. Provides a continuous measure of how close the graph is to being split. |
| **Anomaly signal** | A sharp decrease signals the network is approaching a partitioning event — a direct measure of resilience to targeted attacks or failures. |
| **Code** | `scipy.sparse.linalg.eigsh(L_sparse, k=2, sigma=1e-6, which='LM')` using shift-invert mode for fast convergence. Falls back to `which='SM'`. |
| **Citation** | Fiedler, "Algebraic connectivity of graphs," *Czech. Math. J.* 23 (1973) |

---

### 6 - Spectral Radius

| | |
|---|---|
| **Column** | `spectral_radius` |
| **Type** | float > 0 |
| **Formula** | λ₁(A) — the largest eigenvalue of the adjacency matrix |
| **Interpretation** | Relates to the maximum rate at which information or contagion can spread. Bounded by √(d_max) ≤ λ₁ ≤ d_max. Reflects the influence of the highest-degree transit providers. |
| **Anomaly signal** | A change indicates a shift in hub structure. If a major Tier-1 provider changes peering, or a new super-hub appears (route leak), the spectral radius shifts. |
| **Code** | `eigsh(A_sparse, k=1, which='LM')` |
| **Citation** | Cvetkovic et al., *An Introduction to the Theory of Graph Spectra*, Cambridge (2010) |

---

### 7 - Percolation Limit

| | |
|---|---|
| **Column** | `percolation_limit` |
| **Type** | float > 0 |
| **Formula** | τ_c = 1 / λ₁(A) (inverse of the spectral radius) |
| **Interpretation** | Critical threshold for epidemic spreading. If the effective spreading rate exceeds this, a contagion (routing update, attack) can propagate to a macroscopic fraction of the network. For scale-free networks like the Internet, this threshold is very small. |
| **Anomaly signal** | A decrease (i.e., spectral radius increase) means the network becomes more vulnerable to cascading failures or widespread route propagation (e.g., BGP hijacks spreading globally). |
| **Code** | Derived directly from the spectral radius: `1.0 / spectral_radius` |
| **Citation** | Pastor-Satorras & Vespignani, "Epidemic spreading in scale-free networks," *PRL* 86 (2001) |

---

### 8 - Symmetry Ratio

| | |
|---|---|
| **Columns** | `symmetry_ratio`, `symmetry_ratio_partial` (bool flag) |
| **Type** | float > 0 |
| **Formula** | SR = \|{distinct eigenvalues of A}\| / (D + 1), where D is the diameter |
| **Interpretation** | Structural symmetry of the graph. A ratio of 1 means minimal symmetry (all eigenvalues distinct); lower values indicate more repeated eigenvalues (structural regularity). |
| **Anomaly signal** | A route leak creating many symmetric paths lowers the ratio; loss of a symmetric peering fabric (IXP outage) raises it. |
| **Code** | For graphs with n < 5,000: full eigenvalue decomposition. Otherwise partial (top 50 eigenvalues) with `symmetry_ratio_partial=True`. |
| **Citation** | Dekker, "Network centrality and super-spreaders in infectious disease epidemiology," *CATS 2005* |

---

### 9 - Natural Connectivity

| | |
|---|---|
| **Columns** | `natural_connectivity`, `natural_connectivity_partial` (bool flag) |
| **Type** | float |
| **Formula** | λ̄ = ln[(1/n) Σ exp(λᵢ)], computed with numerical stability as λ_max + ln[(1/n) Σ exp(λᵢ - λ_max)] |
| **Interpretation** | A weighted average of closed-walk counts, providing a robust measure of structural redundancy and fault tolerance. Unlike algebraic connectivity (which focuses on the weakest link), natural connectivity captures overall redundancy. |
| **Anomaly signal** | A sudden decrease indicates loss of redundant paths — the network is becoming more fragile. Captures different failure modes than algebraic connectivity. |
| **Code** | Full spectrum for n < 5,000 (exact). Partial spectrum for larger graphs (approximation dominated by largest eigenvalues). |
| **Citation** | Wu et al., "Natural connectivity of complex networks," *Chinese Physics Letters* 27 (2010) |

---

### 10 - Kirchhoff Index

| | |
|---|---|
| **Column** | `kirchhoff_index` |
| **Type** | float > 0 (or null for large graphs) |
| **Formula** | Kf = n · Σ(1/μ_k), where μ_k are the non-zero Laplacian eigenvalues |
| **Interpretation** | Sum of effective resistances between all node pairs (treating the graph as an electrical network with unit resistors). Lower values = better connected with more parallel paths. |
| **Anomaly signal** | An increase means effective distances between ASes are growing, indicating loss of peering links or transit paths. |
| **Code** | Requires the **full** Laplacian spectrum, so only computed when n < 5,000. Returns `null` otherwise. |
| **Citation** | Klein & Randic, "Resistance distance," *J. Math. Chem.* 12 (1993) |

---

### 11 - Log Number of Spanning Trees

| | |
|---|---|
| **Column** | `log_spanning_trees` |
| **Type** | float (or null for large graphs) |
| **Formula** | By Kirchhoff's matrix tree theorem: log t(G) = Σ ln(μ_k) - ln(n), where μ_k are the non-zero Laplacian eigenvalues |
| **Interpretation** | The number of distinct spanning trees quantifies structural redundancy — how many ways full connectivity can be maintained after edge failures. |
| **Anomaly signal** | A decrease indicates fewer redundant connectivity structures. A fundamental resilience metric capturing how many "backup" topologies exist. |
| **Code** | Requires the **full** Laplacian spectrum, so only computed when n < 5,000. Returns `null` otherwise. |
| **Citation** | Kirchhoff, "Ueber die Auflosung der Gleichungen...," *Annalen der Physik* 148 (1847) |

---

### 12 - Edge and Node Connectivity

| | |
|---|---|
| **Columns** | `edge_connectivity`, `node_connectivity` |
| **Type** | int ≥ 0 |
| **Formula** | Edge connectivity λ(G): min edge cut to disconnect G |
| | Node connectivity κ(G): min node cut to disconnect G |
| | Whitney's theorem: κ(G) ≤ λ(G) ≤ δ(G), where δ is the minimum degree |
| **Interpretation** | The minimum number of edges (or nodes) that must be removed to disconnect the graph. Direct measures of robustness to targeted attacks. |
| **Anomaly signal** | A decrease directly reflects increased vulnerability to partitioning. |
| **Code** | Optimized with structural shortcuts: checks min-degree (if 1 → edge connectivity = 1), bridge detection (`nx.has_bridges`), articulation point detection. Falls back to max-flow only for small graphs or when shortcuts are insufficient. For large graphs, computes flow from the min-degree node to each of its neighbors with a unit-capacity graph copy. |
| **Citation** | Whitney, "Congruent graphs and the connectivity of graphs," *Am. J. Math.* 54 (1932) |

---

### 13 - Rich-Club Coefficient

| | |
|---|---|
| **Columns** | `rich_club_p25`, `rich_club_p50`, `rich_club_p75`, `rich_club_p90`, `rich_club_p95` |
| **Type** | float in [0, 1] |
| **Formula** | φ(k) = 2·E_{>k} / (N_{>k}·(N_{>k}-1)), where N_{>k} is the count of nodes with degree > k and E_{>k} is the edges among them. Computed at degree thresholds at the 25th, 50th, 75th, 90th, and 95th percentiles. Unnormalized. |
| **Interpretation** | How densely interconnected the high-degree "rich" nodes are. A high coefficient at the 95th percentile means Tier-1 and major Tier-2 ASes form a dense core. |
| **Anomaly signal** | Changes at the 90th and 95th percentiles detect disruptions to the core transit fabric. If a major Tier-1 depeers or goes offline, the rich-club coefficient at high percentiles drops. |
| **Code** | `nx.rich_club_coefficient(G_lcc, normalized=False)`, evaluated at nearest available degree to each percentile threshold. |
| **Citation** | Zhou & Mondragon, "The rich-club phenomenon in the Internet topology," *IEEE Comm. Lett.* (2004) |

---

### 14 - Betweenness Centrality Distribution

| | |
|---|---|
| **Columns** | `betweenness_mean`, `betweenness_max`, `betweenness_std`, `betweenness_skewness` |
| **Type** | float |
| **Formula** | For each node v: C_B(v) = Σ σ_st(v)/σ_st, normalized by 1/((n-1)(n-2)). Graph-level output is summary statistics (mean, max, std, skewness) of this distribution. |
| **Interpretation** | How much traffic (under shortest-path routing) flows through each node. High skewness indicates a few nodes dominate as traffic intermediaries (typical hierarchical Internet). The maximum identifies the single most critical AS. |
| **Anomaly signal** | A sudden increase in max betweenness: routing convergence funneling through fewer paths. A decrease in skewness: more balanced routing. |
| **Code** | NetworKit `ApproxBetweenness(epsilon=0.01, delta=0.1)` when available, otherwise NetworkX `betweenness_centrality(k=sample_k)`. **Computed once and stored in `shared_data['_bc_map']`** for reuse by node-level extraction. |
| **Citation** | Brandes, "A faster algorithm for betweenness centrality," *J. Math. Soc.* 25(2) (2001) |

---

### 15 - k-Core Decomposition Metrics

| | |
|---|---|
| **Columns** | `degeneracy`, `core_mean`, `core_std`, `core_median`, `innermost_core_size` |
| **Type** | int (degeneracy, innermost_core_size), float (distribution stats) |
| **Formula** | core(v) = max{k : v ∈ H_k}, where H_k is the maximal subgraph with minimum degree ≥ k. Degeneracy = max core number. Innermost core size = count of nodes at max core number. |
| **Interpretation** | The hierarchical shell structure of the network. The innermost core contains the most interconnected ASes — major Tier-1 and Tier-2 transit providers. |
| **Anomaly signal** | Changes in degeneracy or innermost core size detect structural shifts in the network's core, such as a Tier-1 provider leaving the peering mesh. |
| **Code** | NetworKit `CoreDecomposition()` or NetworkX `core_number()`. **Computed once and stored in `shared_data['_core_map']`** for reuse by node-level extraction. |
| **Citation** | Seidman, "Network structure and minimum degree," *Social Networks* 5(3) (1983) |

---

### 16 - Spectral Gap and Eigenvalue Ratio

| | |
|---|---|
| **Columns** | `spectral_gap`, `adj_eig_ratio_1_2` |
| **Type** | float |
| **Formula** | Spectral gap: Δ = λ₁ - λ₂. Eigenvalue ratio: λ₁/λ₂. Where λ₁, λ₂ are the two largest adjacency eigenvalues. |
| **Interpretation** | The spectral gap controls mixing time of random walks and the rate of information propagation. A large spectral gap means good expansion properties — information spreads quickly and evenly. |
| **Anomaly signal** | A decrease indicates the network is developing community structure or bottlenecks that slow propagation. In BGP terms, the network may be fragmenting into loosely coupled regions. |
| **Code** | Reuses the adjacency eigenvalues from the spectral block (features 8-11). Only computed when `compute_spectral=True`. |
| **Citation** | Chung, *Spectral Graph Theory*, AMS (1997) |

---

## Node-Level Features (10)

These features are extracted by `extract_node_level_features()` (Cell 16). The function returns a DataFrame indexed by ASN with one column per feature, plus an `extra_graph_features` dict (currently containing `radius` from eccentricity).

### 1 - Degree Centrality

| | |
|---|---|
| **Columns** | `degree_centrality`, `degree` |
| **Type** | float in [0, 1] (centrality), int (raw degree) |
| **Formula** | C_D(v) = deg(v) / (n - 1) |
| **Interpretation** | The number of direct peering/transit relationships an AS has. Tier-1 transit providers have the highest degree (thousands of neighbors); stub ASes have very low degree (1-3). |
| **Anomaly signal** | A sudden degree change for an AS: peering dispute (drop), route leak (spike from spurious adjacencies), or hijack (unexpected new neighbors). |
| **Code** | `nx.degree_centrality(G_lcc)` and `G_lcc.degree()` |
| **Citation** | Freeman, "Centrality in social networks conceptual clarification," *Social Networks* 1(3) (1979) |

---

### 2 - Betweenness Centrality

| | |
|---|---|
| **Column** | `betweenness_centrality` |
| **Type** | float in [0, 1] |
| **Formula** | C_B(v) = Σ (σ_st(v)/σ_st) / ((n-1)(n-2)), where σ_st is total shortest paths from s to t, σ_st(v) is those passing through v |
| **Interpretation** | How often an AS lies on shortest paths between other AS pairs. High-betweenness ASes are critical transit points — Tier-1 providers and major IXPs. |
| **Anomaly signal** | A spike for a previously peripheral AS could indicate a route hijack. A drop for a major transit AS: traffic being rerouted around it. |
| **Code** | **Reuses** `shared_data['_bc_map']` from graph-level extraction (no redundant computation). Falls back to `nx.betweenness_centrality()` if shared data is missing. |
| **Citation** | Brandes, *J. Math. Soc.* 25(2) (2001) |

---

### 3 - Closeness Centrality

| | |
|---|---|
| **Column** | `closeness_centrality` |
| **Type** | float in (0, 1] |
| **Formula** | C_C(v) = (n - 1) / Σ d(v, u) |
| **Interpretation** | How close an AS is, on average, to all other ASes. High closeness correlates with being a well-connected transit provider near the "center" of the network. |
| **Anomaly signal** | A change for an AS (vs. its historical baseline) indicates connectivity or routing path changes. A global decrease across many ASes: the network is becoming less compact. |
| **Code** | NetworKit `Closeness(variant=GENERALIZED)` or NetworkX `closeness_centrality(wf_improved=True)` |
| **Citation** | Sabidussi, "The centrality index of a graph," *Psychometrika* 31(4) (1966) |

---

### 4 - Eigenvector Centrality

| | |
|---|---|
| **Column** | `eigenvector_centrality` |
| **Type** | float in [0, 1] |
| **Formula** | x_v = (1/λ₁) Σ x_u for u ∈ N(v). Equivalently, x is the principal eigenvector of A satisfying Ax = λ₁x. |
| **Interpretation** | A node's importance based on the importance of its neighbors. Differentiates between an AS peering with many stubs (high degree, lower eigenvector centrality) and one peering with other major transit providers (lower degree, higher eigenvector centrality). |
| **Anomaly signal** | A sudden increase could indicate new connections to the most important hubs — legitimate new peering or a route hijack making the AS appear central. |
| **Code** | NetworKit `EigenvectorCentrality(tol=1e-8)` or NetworkX `eigenvector_centrality(max_iter=200)` with fallback to `eigenvector_centrality_numpy()` on convergence failure. |
| **Citation** | Bonacich, "Factoring and weighting approaches to status scores and clique identification," *J. Math. Soc.* 2(1) (1972) |

---

### 5 - PageRank

| | |
|---|---|
| **Column** | `pagerank` |
| **Type** | float (sums to 1.0 across all nodes) |
| **Formula** | PR(v) = (1-d)/n + d · Σ PR(u)/deg(u) for u ∈ N(v), where d = 0.85 |
| **Interpretation** | Probability that a random surfer traversing the AS topology is at node v at any given time. Accounts for both the number and quality of connections, with teleportation preventing over-concentration. |
| **Anomaly signal** | Anomalous changes flag structural changes in routing that affect traffic distribution. |
| **Code** | NetworKit `PageRank(damp=0.85, tol=1e-8)` or NetworkX `pagerank(alpha=0.85)` |
| **Citation** | Brin & Page, "The anatomy of a large-scale hypertextual web search engine," *Computer Networks* 30 (1998) |

---

### 6 - Local Clustering Coefficient

| | |
|---|---|
| **Column** | `local_clustering` |
| **Type** | float in [0, 1] |
| **Formula** | C(v) = 2·tri(v) / (deg(v)(deg(v)-1)). For deg(v) < 2, C(v) = 0. |
| **Interpretation** | How densely interconnected an AS's neighbors are. High values are common at IXPs (dense peering mesh). Low values characterize transit providers whose customers don't peer with each other. |
| **Anomaly signal** | Changes for specific ASes (especially IXP participants or regional peering hubs) detect peering mesh changes or peering disputes. |
| **Code** | NetworKit `LocalClusteringCoefficient(turbo=True)` or NetworkX `clustering()` |
| **Citation** | Watts & Strogatz, *Nature* 393 (1998) |

---

### 7 - Average Neighbor Degree

| | |
|---|---|
| **Column** | `avg_neighbor_degree` |
| **Type** | float |
| **Formula** | k_nn(v) = (1/deg(v)) Σ deg(u) for u ∈ N(v) |
| **Interpretation** | Whether a node connects to high-degree or low-degree neighbors. In the disassortative Internet, stub ASes (low degree) tend to have high average neighbor degree (connected to large transit providers), while transit providers have lower average neighbor degree. |
| **Anomaly signal** | Changes indicate neighborhood shifts — e.g., losing a connection to a large transit provider lowers k_nn, or gaining connections to many new small networks. |
| **Code** | `nx.average_neighbor_degree(G_lcc)` |
| **Citation** | Pastor-Satorras et al., "Dynamical and correlation properties of the Internet," *PRL* 87 (2001) |

---

### 8 - Node Clique Number

| | |
|---|---|
| **Column** | `node_clique_number` |
| **Type** | int ≥ 1 |
| **Formula** | ω(v) = max{\|C\| : v ∈ C, C is a clique} |
| **Interpretation** | Size of the largest complete subgraph containing this AS. Large clique numbers indicate participation in dense peering meshes (e.g., IXP route server peering). |
| **Anomaly signal** | A sudden increase could indicate a route leak creating apparent fully-meshed structures. |
| **Code** | Exact `nx.node_clique_number()` for n ≤ 5,000 (configurable via `max_nodes_for_clique`). For larger graphs, uses exact computation on the innermost k-core and a **greedy approximation** for remaining nodes (sorted by degree, greedily extend clique). |
| **Citation** | Karp, "Reducibility among Combinatorial Problems," Springer (1972) |

---

### 9 - Eccentricity

| | |
|---|---|
| **Column** | `eccentricity` |
| **Type** | int |
| **Formula** | ε(v) = max d(v, u) over all u ∈ V |
| **Interpretation** | Maximum shortest-path distance from this AS to any other node. Central Internet core nodes have low eccentricity; peripheral stub ASes have high eccentricity. |
| **Extra output** | The graph **radius** (min eccentricity) is returned in `extra_graph_features['radius']`. |
| **Anomaly signal** | A sudden increase for a previously central AS: its direct paths to distant parts of the network have been disrupted. |
| **Code** | NetworKit BFS for all nodes (C++, ~10-50x faster). Falls back to NetworkX `eccentricity()` for n < 10,000, or sample-based (500 nodes) for larger graphs. |
| **Citation** | Standard graph theory definition |

---

### 10 - Core Number (k-Shell)

| | |
|---|---|
| **Column** | `core_number` |
| **Type** | int ≥ 0 |
| **Formula** | core(v) = max{k : v ∈ H_k}, where H_k is the maximal subgraph with minimum degree ≥ k. Computed by iteratively removing nodes with degree < k. |
| **Interpretation** | Position in the network's hierarchical shell structure. Innermost core (highest k-shell): Tier-1 and major Tier-2 providers. Outermost shells (k=1): single-homed stub networks. |
| **Anomaly signal** | A change in an AS's core number indicates a fundamental structural position shift. A stub AS suddenly in a high k-shell could signal a route leak or hijack. |
| **Code** | **Reuses** `shared_data['_core_map']` from graph-level extraction. Falls back to `nx.core_number()` if shared data is missing. |
| **Citation** | Seidman, "Network structure and minimum degree," *Social Networks* 5(3) (1983) |

---

## Quick Reference Tables

### Graph-Level Features

| # | Feature | Output Column(s) | Type |
|---|---------|-------------------|------|
| 1 | Assortativity | `assortativity` | float |
| 2 | Density | `density` | float |
| 3 | Clustering | `clustering_global`, `clustering_avg_local` | float |
| 4 | Diameter / Avg Path | `diameter`, `avg_path_length` | int / float |
| 5 | Algebraic Connectivity | `algebraic_connectivity` | float |
| 6 | Spectral Radius | `spectral_radius` | float |
| 7 | Percolation Limit | `percolation_limit` | float |
| 8 | Symmetry Ratio | `symmetry_ratio` | float |
| 9 | Natural Connectivity | `natural_connectivity` | float |
| 10 | Kirchhoff Index | `kirchhoff_index` | float |
| 11 | Log Spanning Trees | `log_spanning_trees` | float |
| 12 | Connectivity | `edge_connectivity`, `node_connectivity` | int |
| 13 | Rich-Club | `rich_club_p25` ... `rich_club_p95` | float |
| 14 | Betweenness Dist. | `betweenness_mean/max/std/skewness` | float |
| 15 | k-Core Metrics | `degeneracy`, `core_mean/std/median`, `innermost_core_size` | int/float |
| 16 | Spectral Gap | `spectral_gap`, `adj_eig_ratio_1_2` | float |

### Node-Level Features

| # | Feature | Output Column(s) | Type |
|---|---------|-------------------|------|
| 1 | Degree Centrality | `degree_centrality`, `degree` | float / int |
| 2 | Betweenness | `betweenness_centrality` | float |
| 3 | Closeness | `closeness_centrality` | float |
| 4 | Eigenvector | `eigenvector_centrality` | float |
| 5 | PageRank | `pagerank` | float |
| 6 | Local Clustering | `local_clustering` | float |
| 7 | Avg Neighbor Degree | `avg_neighbor_degree` | float |
| 8 | Clique Number | `node_clique_number` | int |
| 9 | Eccentricity | `eccentricity` | int |
| 10 | Core Number | `core_number` | int |

---

## Implementation Notes

### Performance Optimization

The pipeline uses a **dual-backend** strategy:

- **NetworKit** (C++): Used when available for clustering, diameter, betweenness, closeness, eigenvector centrality, PageRank, local clustering, core decomposition, and BFS-based eccentricity. Typically 10-50x faster than NetworkX on large graphs.
- **NetworkX** (Python): Used as a fallback and for algorithms not available in NetworKit (assortativity, rich-club, connectivity, clique number).

### Shared Data Pattern

Expensive computations are performed **once** and shared between graph-level and node-level extraction via the `shared_data` dictionary:

- `shared_data['_bc_map']` — betweenness centrality scores (computed in graph-level feature 14, reused in node-level feature 2)
- `shared_data['_core_map']` — k-core numbers (computed in graph-level feature 15, reused in node-level feature 10)
- `shared_data['degrees']` — degree list

### Spectral Computation

Spectral features (5, 6, 8-11, 16) use `scipy.sparse.linalg.eigsh` on sparse matrices:

- **Shift-invert mode** (`sigma=1e-6, which='LM'`) for Laplacian eigenvalues near zero — avoids ARPACK convergence issues with `which='SM'` on singular matrices.
- **Full spectrum** for graphs with n < 5,000 (required for exact Kirchhoff index and spanning tree count).
- **Partial spectrum** (top 50 eigenvalues) for larger graphs, with `_partial` flags indicating approximation.

### Large Graph Handling

| Feature | Small graph (exact) | Large graph (optimized) |
|---------|---------------------|------------------------|
| Avg path length | All-pairs shortest paths | 500-node BFS sample |
| Diameter | Exact | NetworKit or 100-node sample |
| Edge connectivity | `nx.edge_connectivity()` | Structural shortcuts + min-degree flow |
| Node connectivity | `nx.node_connectivity()` | Articulation point check + min-degree local connectivity |
| Kirchhoff index | Full Laplacian spectrum | Skipped (null) |
| Spanning trees | Full Laplacian spectrum | Skipped (null) |
| Clique number | Exact NP-hard solver | Exact on innermost k-core + greedy on rest |
| Eccentricity | All-nodes BFS | NetworKit BFS (all nodes) or 500-node sample |
