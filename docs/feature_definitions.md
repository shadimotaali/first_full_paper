# BGP Graph Feature Definitions

Complete reference for all graph-theoretic features extracted from the BGP AS-level topology by the `bgp_graph_features.ipynb` pipeline.

---

## Graph-Level Features (16 features)

### 1. Assortativity

| | |
|---|---|
| **Column** | `assortativity` |
| **Type** | float, range [-1, 1] |
| **Formula** | Pearson correlation of degrees at the two endpoints of every edge: $r = \frac{M \sum_i j_i k_i - (\sum_i j_i)(\sum_i k_i)}{\sqrt{M \sum_i j_i^2 - (\sum_i j_i)^2} \cdot \sqrt{M \sum_i k_i^2 - (\sum_i k_i)^2}}$ where $j_i, k_i$ are degrees of endpoints of edge $i$, and $M = |E|$. |
| **Meaning** | Whether high-degree nodes preferentially connect to other high-degree nodes (assortative, $r > 0$) or to low-degree nodes (disassortative, $r < 0$). The Internet AS topology is famously disassortative: large transit providers connect to many stub ASes. |
| **Anomaly relevance** | A sudden shift could indicate a major transit provider going down (more assortative) or a large-scale route leak flooding connections between hierarchy tiers. |
| **Citation** | Newman, M. E. J. "Assortative mixing in networks." *Physical Review Letters* 89, 208701 (2002). |

---

### 2. Density

| | |
|---|---|
| **Column** | `density` |
| **Type** | float, range [0, 1] |
| **Formula** | $\rho = \frac{2|E|}{|V|(|V|-1)}$ |
| **Meaning** | Ratio of actual edges to the maximum possible edges. The AS-level Internet is extremely sparse (density on the order of $10^{-4}$ to $10^{-5}$). |
| **Anomaly relevance** | A noticeable change indicates either many new peering relationships appearing (e.g., an IXP adding members) or many links disappearing (e.g., a large-scale outage). |
| **Citation** | Standard graph theory definition. |

---

### 3. Clustering Coefficient (Global and Average Local)

| | |
|---|---|
| **Columns** | `clustering_global`, `clustering_avg_local` |
| **Type** | float, range [0, 1] |
| **Formula** | Global (transitivity): $C_{global} = \frac{3 \times \text{triangles}}{\text{connected triples}}$ |
| | Average local: $C_{avg} = \frac{1}{n} \sum_{v \in V} C(v)$, where $C(v) = \frac{2 \cdot \text{tri}(v)}{\deg(v)(\deg(v)-1)}$ |
| **Meaning** | The tendency of neighbors of a node to also be neighbors of each other. High clustering reflects dense peering clusters (e.g., IXP meshes), while low clustering characterizes hierarchical transit relationships. |
| **Anomaly relevance** | A sudden drop could indicate a peering fabric disruption (e.g., IXP failure). An increase might signal new dense peering arrangements or artificial route injection creating clique-like structures. |
| **Citation** | Watts, D. J. & Strogatz, S. H. "Collective dynamics of 'small-world' networks." *Nature* 393, 440-442 (1998). |

---

### 4. Diameter and Average Path Length

| | |
|---|---|
| **Columns** | `diameter`, `avg_path_length` |
| **Type** | int (diameter), float (avg path length) |
| **Formula** | Diameter: $D = \max_{u,v \in V} d(u,v)$ |
| | Average path length: $L = \frac{1}{n(n-1)} \sum_{u \neq v} d(u,v)$ |
| **Meaning** | Worst-case (diameter) and typical (average) number of AS hops between any two ASes. The AS Internet has small-world properties: diameter around 10-15, average path length around 3-4, despite 70,000+ nodes. For large graphs ($n \geq 20000$), average path length is estimated by sampling 500 source nodes. |
| **Anomaly relevance** | An increase suggests the network is becoming less well-connected (loss of critical transit links or partitioning). A decrease could indicate the appearance of shortcut peering links. |
| **Citation** | Watts, D. J. & Strogatz, S. H. "Collective dynamics of 'small-world' networks." *Nature* 393, 440-442 (1998). |

---

### 5. Algebraic Connectivity (Fiedler Value)

| | |
|---|---|
| **Column** | `algebraic_connectivity` |
| **Type** | float, $\geq 0$ |
| **Formula** | $\mu_2(L)$, the second-smallest eigenvalue of the graph Laplacian $L = D - A$, where $D$ is the diagonal degree matrix and $A$ is the adjacency matrix. |
| **Meaning** | How well-connected the graph is. A larger Fiedler value means the graph is harder to disconnect. It is 0 if and only if the graph is disconnected. Provides a continuous measure of how close the graph is to being split into two components. |
| **Anomaly relevance** | A sharp decrease signals the network is becoming fragile or approaching a partitioning event -- a direct measure of the Internet's resilience to targeted attacks or failures. |
| **Implementation note** | Computed via `scipy.sparse.linalg.eigsh` with `which='SM'` on the sparse Laplacian, rather than NetworkX's `tracemin_pcg` method which is orders of magnitude slower on large graphs. |
| **Citation** | Fiedler, M. "Algebraic connectivity of graphs." *Czechoslovak Mathematical Journal* 23(98), 298-305 (1973). |

---

### 6. Spectral Radius

| | |
|---|---|
| **Column** | `spectral_radius` |
| **Type** | float, $> 0$ |
| **Formula** | $\lambda_1(A)$, the largest eigenvalue of the adjacency matrix. Computed via `scipy.sparse.linalg.eigsh(A, k=1, which='LM')`. |
| **Meaning** | Relates to the maximum rate at which information (or a contagion) can spread across the network. Bounded by $\sqrt{d_{max}} \leq \lambda_1 \leq d_{max}$. In the AS topology, reflects the influence of the highest-degree transit providers. |
| **Anomaly relevance** | A change indicates a shift in the hub structure of the network. If a major Tier-1 provider changes its peering, or a new super-hub appears (e.g., via route leak), the spectral radius shifts. |
| **Citation** | Cvetkovic, D., Rowlinson, P. & Simic, S. *An Introduction to the Theory of Graph Spectra.* Cambridge University Press (2010). |

---

### 7. Percolation Limit (Epidemic Threshold)

| | |
|---|---|
| **Column** | `percolation_limit` |
| **Type** | float, $> 0$ |
| **Formula** | $\tau_c = 1 / \lambda_1(A)$, inverse of the spectral radius. |
| **Meaning** | The critical threshold for epidemic spreading. If the effective spreading rate exceeds this threshold, a contagion (routing update, attack) can propagate to a macroscopic fraction of the network. For scale-free networks like the Internet, this threshold is very small. |
| **Anomaly relevance** | A decrease (i.e., increase in spectral radius) means the network becomes even more vulnerable to cascading failures or widespread route propagation events (e.g., BGP hijacks that spread globally). |
| **Citation** | Pastor-Satorras, R. & Vespignani, A. "Epidemic spreading in scale-free networks." *Physical Review Letters* 86, 3200 (2001). |

---

### 8. Symmetry Ratio

| | |
|---|---|
| **Column** | `symmetry_ratio` (also `symmetry_ratio_partial` flag) |
| **Type** | float, $> 0$ |
| **Formula** | $SR = \frac{|\{\text{distinct eigenvalues of } A\}|}{D + 1}$ where $D$ is the graph diameter. |
| **Meaning** | Structural symmetry of the graph. A ratio of 1 means minimal symmetry (all eigenvalues distinct); lower values indicate more structural symmetry (repeated eigenvalues). For graphs with $n \geq 5000$, only a partial spectrum is computed and the result is approximate. |
| **Anomaly relevance** | A route leak creating many symmetric paths would lower this ratio; loss of a symmetric peering fabric (e.g., IXP outage) would increase it. |
| **Citation** | Dekker, A. H. "Network centrality and super-spreaders in infectious disease epidemiology." *CATS 2005*, CRPIT 41. |

---

### 9. Natural Connectivity

| | |
|---|---|
| **Column** | `natural_connectivity` |
| **Type** | float |
| **Formula** | $\bar{\lambda} = \ln\left[\frac{1}{n} \sum_{i=1}^{n} e^{\lambda_i}\right]$ where $\lambda_i$ are the eigenvalues of $A$. Computed with a numerical stability trick: $\bar{\lambda} = \lambda_{max} + \ln\left[\frac{1}{n} \sum e^{(\lambda_i - \lambda_{max})}\right]$. |
| **Meaning** | A weighted average of closed-walk counts, providing a robust measure of the network's structural redundancy and fault tolerance. Unlike algebraic connectivity (which focuses on the weakest link), natural connectivity captures overall redundancy across the entire graph. |
| **Anomaly relevance** | A sudden decrease indicates loss of redundant paths, meaning the network is becoming more fragile. Captures different failure modes than algebraic connectivity. |
| **Citation** | Wu, J. et al. "Natural connectivity of complex networks." *Chinese Physics Letters* 27, 078902 (2010). |

---

### 10. Kirchhoff Index

| | |
|---|---|
| **Column** | `kirchhoff_index` |
| **Type** | float, $> 0$ |
| **Formula** | $Kf = n \sum_{k=2}^{n} \frac{1}{\mu_k}$ where $\mu_k$ are the non-zero eigenvalues of the Laplacian $L$. |
| **Meaning** | Sum of effective resistances between all pairs of nodes (treating the graph as an electrical network with unit resistors). Lower values mean the network is better connected with more parallel paths. |
| **Anomaly relevance** | An increase means effective distances between ASes are growing, potentially indicating loss of peering links or transit paths. A global resilience metric complementary to algebraic connectivity. |
| **Citation** | Klein, D. J. & Randic, M. "Resistance distance." *Journal of Mathematical Chemistry* 12, 81-95 (1993). |

---

### 11. Log Number of Spanning Trees

| | |
|---|---|
| **Column** | `log_spanning_trees` |
| **Type** | float (or null for large graphs) |
| **Formula** | By Kirchhoff's matrix tree theorem: $t(G) = \frac{1}{n} \prod_{k=2}^{n} \mu_k$. Stored as $\log t(G) = \sum_{k=2}^{n} \ln(\mu_k) - \ln(n)$. |
| **Meaning** | The number of distinct spanning trees quantifies structural redundancy -- how many ways full connectivity can be maintained after edge failures. Only computed when the full spectrum is available ($n < 5000$). |
| **Anomaly relevance** | A decrease indicates fewer redundant connectivity structures. A fundamental resilience metric that captures how many "backup" topologies exist. |
| **Citation** | Kirchhoff, G. "Ueber die Auflosung der Gleichungen..." *Annalen der Physik* 148(12), 497-508 (1847). |

---

### 12. Edge and Node Connectivity

| | |
|---|---|
| **Columns** | `edge_connectivity`, `node_connectivity` |
| **Type** | int, $\geq 0$ |
| **Formula** | Edge connectivity: $\lambda(G) = \min |S|$ such that removing edge set $S$ disconnects $G$. |
| | Node connectivity: $\kappa(G) = \min |S|$ such that removing node set $S$ disconnects $G$. |
| | Whitney's theorem: $\kappa(G) \leq \lambda(G) \leq \delta(G)$ where $\delta$ is the minimum degree. |
| **Meaning** | The minimum number of edges (or nodes) that must be removed to disconnect the graph. Direct measures of robustness to targeted attacks. Node connectivity corresponds to how many critical ASes must be compromised to partition the Internet. |
| **Anomaly relevance** | A decrease directly reflects increased vulnerability to partitioning. |
| **Citation** | Whitney, H. "Congruent graphs and the connectivity of graphs." *American Journal of Mathematics* 54, 150-168 (1932). |

---

### 13. Rich-Club Coefficient

| | |
|---|---|
| **Columns** | `rich_club_p25`, `rich_club_p50`, `rich_club_p75`, `rich_club_p90`, `rich_club_p95` |
| **Type** | float, range [0, 1] |
| **Formula** | $\phi(k) = \frac{2 E_{>k}}{N_{>k}(N_{>k}-1)}$ where $N_{>k}$ is the number of nodes with degree $> k$ and $E_{>k}$ is the number of edges among them. Computed at degree thresholds corresponding to the 25th, 50th, 75th, 90th, and 95th percentiles. Unnormalized. |
| **Meaning** | How densely interconnected the high-degree nodes ("rich" nodes) are. A high rich-club coefficient at the 95th percentile means Tier-1 and major Tier-2 ASes form a dense core. |
| **Anomaly relevance** | Changes at the 90th and 95th percentiles can detect disruptions to the core transit fabric. If a major Tier-1 provider depeers or goes offline, the rich-club coefficient at high percentiles drops. |
| **Citation** | Zhou, S. & Mondragon, R. J. "The rich-club phenomenon in the Internet topology." *IEEE Communications Letters* 8(3), 180-182 (2004). |

---

### 14. Betweenness Centrality Distribution

| | |
|---|---|
| **Columns** | `betweenness_mean`, `betweenness_max`, `betweenness_std`, `betweenness_skewness` |
| **Type** | float |
| **Formula** | For each node $v$: $C_B(v) = \sum_{s \neq v \neq t} \frac{\sigma_{st}(v)}{\sigma_{st}}$, normalized by $\frac{1}{(n-1)(n-2)}$. The graph-level features are summary statistics (mean, max, std, skewness) of this distribution. |
| **Meaning** | How much traffic (assuming shortest-path routing) flows through each node. High skewness indicates a few nodes dominate as traffic intermediaries (typical of the Internet's hierarchical structure). The maximum identifies the single most critical AS. |
| **Anomaly relevance** | A sudden increase in max betweenness could indicate routing convergence funneling through fewer paths. A decrease in skewness indicates more balanced routing. |
| **Implementation note** | When NetworKit is available, `ApproxBetweenness(epsilon=0.01, delta=0.1)` is used. Otherwise, NetworkX's sampled betweenness with $k=500$ pivots. Computed once and shared with node-level extraction via `shared_data['_bc_map']`. |
| **Citation** | Brandes, U. "A faster algorithm for betweenness centrality." *Journal of Mathematical Sociology* 25(2), 163-177 (2001). |

---

### 15. k-Core Decomposition Metrics

| | |
|---|---|
| **Columns** | `degeneracy`, `core_mean`, `core_std`, `core_median`, `innermost_core_size` |
| **Type** | int (degeneracy, innermost_core_size), float (distribution stats) |
| **Formula** | Core number: $\text{core}(v) = \max\{k : v \in H_k\}$ where $H_k$ is the maximal subgraph with minimum degree $\geq k$. |
| | Degeneracy: $k_{max} = \max_v \text{core}(v)$. Innermost core size: $|\{v : \text{core}(v) = k_{max}\}|$. |
| **Meaning** | The hierarchical shell structure of the network. The innermost core (highest k-shell) contains the most interconnected ASes -- major Tier-1 and Tier-2 transit providers. |
| **Anomaly relevance** | Changes in degeneracy or innermost core size detect structural shifts in the network's core, such as a Tier-1 provider leaving the peering mesh. |
| **Implementation note** | Computed once and shared with node-level extraction via `shared_data['_core_map']`. |
| **Citation** | Seidman, S. B. "Network structure and minimum degree." *Social Networks* 5(3), 269-287 (1983). |

---

### 16. Spectral Gap and Eigenvalue Ratio

| | |
|---|---|
| **Columns** | `spectral_gap`, `adj_eig_ratio_1_2` |
| **Type** | float |
| **Formula** | Spectral gap: $\Delta = \lambda_1 - \lambda_2$. Eigenvalue ratio: $\lambda_1 / \lambda_2$. Where $\lambda_1, \lambda_2$ are the two largest eigenvalues of $A$. |
| **Meaning** | The spectral gap controls mixing time of random walks and the rate of information propagation. A large spectral gap means good expansion properties -- information spreads quickly and evenly. |
| **Anomaly relevance** | A decrease indicates the network is developing community structure or bottlenecks that slow information propagation. In BGP terms, this could mean the network is fragmenting into loosely coupled regions. |
| **Citation** | Chung, F. R. K. *Spectral Graph Theory.* CBMS Regional Conference Series in Mathematics, AMS (1997). |

---

## Node-Level Features (10 features)

### 1. Degree Centrality (and Raw Degree)

| | |
|---|---|
| **Columns** | `degree_centrality`, `degree` |
| **Type** | float (centrality, range [0,1]), int (raw degree) |
| **Formula** | $C_D(v) = \frac{\deg(v)}{n - 1}$ |
| **Meaning** | The number of direct peering/transit relationships an AS has. Tier-1 transit providers have the highest degree (thousands of neighbors), stub ASes have very low degree (often 1-3). |
| **Anomaly relevance** | A sudden change in an AS's degree could indicate a peering dispute (drop), route leak (spike from spurious adjacencies), or hijack (new unexpected neighbors). |
| **Citation** | Freeman, L. C. "Centrality in social networks conceptual clarification." *Social Networks* 1(3), 215-239 (1979). |

---

### 2. Betweenness Centrality

| | |
|---|---|
| **Column** | `betweenness_centrality` |
| **Type** | float, range [0, 1] |
| **Formula** | $C_B(v) = \frac{\sum_{s \neq v \neq t} \sigma_{st}(v) / \sigma_{st}}{(n-1)(n-2)}$ where $\sigma_{st}$ is the total number of shortest paths from $s$ to $t$, and $\sigma_{st}(v)$ is the number passing through $v$. |
| **Meaning** | How often an AS lies on shortest paths between other AS pairs. High betweenness ASes are critical transit points -- Tier-1 providers and major IXPs. |
| **Anomaly relevance** | A sudden spike for a previously peripheral AS could indicate a route hijack (the hijacker appears on many shortest paths). A drop for a major transit AS could indicate traffic being rerouted around it. |
| **Implementation note** | Reuses the `_bc_map` computed during graph-level feature extraction to avoid redundant computation. |
| **Citation** | Brandes, U. "A faster algorithm for betweenness centrality." *Journal of Mathematical Sociology* 25(2), 163-177 (2001). |

---

### 3. Closeness Centrality

| | |
|---|---|
| **Column** | `closeness_centrality` |
| **Type** | float, range (0, 1] |
| **Formula** | $C_C(v) = \frac{n - 1}{\sum_{u \neq v} d(v, u)}$ |
| **Meaning** | How close an AS is, on average, to all other ASes. High closeness correlates with being a well-connected transit provider near the "center" of the network. |
| **Anomaly relevance** | A change for an AS (relative to its historical baseline) could indicate changes in connectivity or routing paths. A global decrease across many ASes suggests the network is becoming less compact. |
| **Citation** | Sabidussi, G. "The centrality index of a graph." *Psychometrika* 31(4), 581-603 (1966). |

---

### 4. Eigenvector Centrality

| | |
|---|---|
| **Column** | `eigenvector_centrality` |
| **Type** | float, range [0, 1] |
| **Formula** | $x_v = \frac{1}{\lambda_1} \sum_{u \in N(v)} x_u$. Equivalently, $x$ is the principal eigenvector of $A$ satisfying $Ax = \lambda_1 x$. |
| **Meaning** | A node's importance based on the importance of its neighbors. Differentiates between an AS that peers with many stubs (high degree, lower eigenvector centrality) and one that peers with other major transit providers. |
| **Anomaly relevance** | A sudden increase could indicate connections to the most important hubs -- potentially legitimate new peering, or a route hijack making the AS appear central. |
| **Citation** | Bonacich, P. "Factoring and weighting approaches to status scores and clique identification." *Journal of Mathematical Sociology* 2(1), 113-120 (1972). |

---

### 5. PageRank

| | |
|---|---|
| **Column** | `pagerank` |
| **Type** | float, sums to 1.0 across all nodes |
| **Formula** | $PR(v) = \frac{1-d}{n} + d \sum_{u \in N(v)} \frac{PR(u)}{\deg(u)}$ where $d = 0.85$ is the damping factor. |
| **Meaning** | The probability that a random surfer traversing the AS topology would be at node $v$ at any given time. Accounts for both the number and quality of connections, with teleportation preventing over-concentration. |
| **Anomaly relevance** | Anomalous changes in an AS's PageRank flag structural changes in routing that affect traffic distribution. |
| **Citation** | Brin, S. & Page, L. "The anatomy of a large-scale hypertextual web search engine." *Computer Networks and ISDN Systems* 30(1-7), 107-117 (1998). |

---

### 6. Local Clustering Coefficient

| | |
|---|---|
| **Column** | `local_clustering` |
| **Type** | float, range [0, 1] |
| **Formula** | $C(v) = \frac{2 \cdot \text{tri}(v)}{\deg(v)(\deg(v) - 1)}$. For nodes with $\deg(v) < 2$, $C(v) = 0$. |
| **Meaning** | How densely interconnected an AS's neighbors are. High values are common at IXPs (dense peering mesh). Low values characterize transit providers whose customers don't peer with each other. |
| **Anomaly relevance** | Changes for specific ASes (especially IXP participants or regional peering hubs) can detect peering mesh changes, new IXP memberships, or peering disputes. |
| **Citation** | Watts, D. J. & Strogatz, S. H. "Collective dynamics of 'small-world' networks." *Nature* 393, 440-442 (1998). |

---

### 7. Average Neighbor Degree

| | |
|---|---|
| **Column** | `avg_neighbor_degree` |
| **Type** | float |
| **Formula** | $k_{nn}(v) = \frac{1}{\deg(v)} \sum_{u \in N(v)} \deg(u)$ |
| **Meaning** | Whether a node connects to high-degree or low-degree neighbors. In the disassortative Internet, stub ASes (low degree) tend to have high average neighbor degree (they connect to large transit providers), while transit providers have lower average neighbor degree. |
| **Anomaly relevance** | Changes for a specific AS indicate changes in its neighborhood -- e.g., losing a connection to a large transit provider (lowers $k_{nn}$) or gaining connections to many new small networks. |
| **Citation** | Pastor-Satorras, R., Vazquez, A. & Vespignani, A. "Dynamical and correlation properties of the Internet." *Physical Review Letters* 87, 258701 (2001). |

---

### 8. Node Clique Number

| | |
|---|---|
| **Column** | `node_clique_number` |
| **Type** | int, $\geq 1$ |
| **Formula** | $\omega(v) = \max\{|C| : v \in C, C \text{ is a clique}\}$ |
| **Meaning** | The size of the largest complete subgraph containing this AS. Large clique numbers indicate participation in dense peering meshes (e.g., IXP route server peering). Finding the maximum clique is NP-hard, so for large graphs ($n > 5000$) a greedy approximation is used with exact computation restricted to the innermost k-core. |
| **Anomaly relevance** | A sudden increase could indicate a route leak creating apparent fully-meshed structures, or the emergence of a new dense peering arrangement. |
| **Citation** | Karp, R. M. "Reducibility among Combinatorial Problems." In *Complexity of Computer Computations*, Springer (1972). |

---

### 9. Eccentricity

| | |
|---|---|
| **Column** | `eccentricity` |
| **Type** | int |
| **Formula** | $\epsilon(v) = \max_{u \in V} d(v, u)$ |
| **Meaning** | The maximum shortest-path distance from this AS to any other node. Central Internet core nodes have low eccentricity; peripheral stub ASes have high eccentricity. The graph radius ($\min_v \epsilon(v)$) is also extracted as an extra graph-level feature. |
| **Anomaly relevance** | A sudden increase for a previously central AS indicates that its direct paths to distant parts of the network have been disrupted. Global increases suggest the network diameter is growing. |
| **Implementation note** | For large graphs ($n \geq 30000$ without NetworKit), only a sample of 500 nodes is computed. |
| **Citation** | Standard graph theory definition. |

---

### 10. Core Number (k-Shell)

| | |
|---|---|
| **Column** | `core_number` |
| **Type** | int, $\geq 0$ |
| **Formula** | $\text{core}(v) = \max\{k : v \in H_k\}$ where $H_k$ is the maximal subgraph with minimum degree $\geq k$. The k-core $H_k$ is obtained by iteratively removing all nodes with degree $< k$. |
| **Meaning** | Position in the network's hierarchical shell structure. ASes in the innermost core (highest k-shell) are the most deeply embedded -- Tier-1 and major Tier-2 providers. ASes in the outermost shells ($k=1$) are the most peripheral -- single-homed stub networks. |
| **Anomaly relevance** | A change in an AS's core number indicates a fundamental shift in its structural position. A stub AS suddenly appearing in a high k-shell could indicate a route leak or hijack where the AS appears to have many new links. |
| **Implementation note** | Reuses the `_core_map` computed during graph-level feature extraction to avoid redundant computation. |
| **Citation** | Seidman, S. B. "Network structure and minimum degree." *Social Networks* 5(3), 269-287 (1983). |

---

## Quick Reference Table

### Graph-Level Features

| # | Feature | Column(s) | Type |
|---|---------|-----------|------|
| 1 | Assortativity | `assortativity` | float |
| 2 | Density | `density` | float |
| 3 | Clustering | `clustering_global`, `clustering_avg_local` | float |
| 4 | Diameter / Avg Path | `diameter`, `avg_path_length` | int / float |
| 5 | Algebraic Connectivity | `algebraic_connectivity` | float |
| 6 | Spectral Radius | `spectral_radius` | float |
| 7 | Percolation Limit | `percolation_limit` | float |
| 8 | Symmetry Ratio | `symmetry_ratio`, `symmetry_ratio_partial` | float / bool |
| 9 | Natural Connectivity | `natural_connectivity` | float |
| 10 | Kirchhoff Index | `kirchhoff_index` | float |
| 11 | Log Spanning Trees | `log_spanning_trees` | float |
| 12 | Connectivity | `edge_connectivity`, `node_connectivity` | int |
| 13 | Rich-Club | `rich_club_p25` ... `rich_club_p95` | float |
| 14 | Betweenness Dist. | `betweenness_mean/max/std/skewness` | float |
| 15 | k-Core Metrics | `degeneracy`, `core_mean/std/median`, `innermost_core_size` | int / float |
| 16 | Spectral Gap | `spectral_gap`, `adj_eig_ratio_1_2` | float |

### Node-Level Features

| # | Feature | Column(s) | Type |
|---|---------|-----------|------|
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
