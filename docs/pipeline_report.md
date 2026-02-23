# BGP AS-Level Topology: Graph Feature Extraction Pipeline

A comprehensive report on the design, implementation, and purpose of the `scripts/bgp_graph_features.ipynb` notebook.

---

## 1. What This Pipeline Does

This notebook implements a complete data pipeline that transforms raw BGP routing data into structured, time-series graph-theoretic features suitable for anomaly detection in Internet routing.

The Internet's inter-domain routing system is built on BGP (Border Gateway Protocol), where tens of thousands of Autonomous Systems (ASes) exchange reachability information. Each AS -- whether a large transit provider like Cogent (AS 174), an enterprise, or a content delivery network -- maintains routing tables that describe how to reach every IP prefix on the Internet. These routing tables encode the AS-level topology: which ASes are directly connected and how traffic flows between them.

This pipeline takes periodic snapshots of these routing tables, reconstructs the AS-level topology graph from each snapshot, and extracts a rich set of graph-theoretic features. The result is a time series of structural measurements that can be monitored for anomalies -- sudden structural changes that may indicate BGP hijacks, route leaks, outages, or other routing events.

---

## 2. Why This Matters

BGP was designed in the 1980s with implicit trust between operators. It has no built-in mechanism to verify that a route announcement is legitimate. This makes BGP vulnerable to:

- **Hijacks**: An AS falsely announces ownership of IP prefixes belonging to another AS, redirecting traffic through itself (for interception, blackholing, or cryptocurrency theft).
- **Route leaks**: An AS improperly propagates routes learned from one peer to another, violating intended routing policies and potentially causing traffic to flow through unintended paths.
- **Outages**: Cable cuts, equipment failures, or configuration errors that remove links from the topology, potentially fragmenting connectivity.
- **State-level interference**: Governments have used BGP manipulation to redirect or censor traffic at national scale.

Traditional detection approaches focus on the control plane (monitoring BGP UPDATE messages for specific prefix-level anomalies). Our approach is complementary: we monitor the *structural properties of the entire topology graph*. A BGP hijack that injects thousands of false routes doesn't just affect individual prefixes -- it changes the graph's degree distribution, centrality structure, clustering, and spectral properties in measurable ways.

By tracking 16 graph-level features and 10 node-level features across time, we create a multi-dimensional "structural fingerprint" of the Internet. Deviations from this fingerprint's normal behavior signal anomalies worth investigating.

---

## 3. Data Source

### RIPE RIS (Routing Information Service)

RIPE NCC operates the **Routing Information Service (RIS)**, a global network of BGP route collectors. Each collector (e.g., `rrc00` in Amsterdam, `rrc04` in Geneva) peers with dozens of BGP routers worldwide and passively records routing information.

The data comes in two forms:
- **RIB dumps** (`bview.*`): Complete routing table snapshots, produced every **8 hours** (at 00:00, 08:00, 16:00 UTC). Each dump captures the full set of routes known to the collector at that instant.
- **UPDATE files** (`updates.*`): Real-time stream of BGP announcements and withdrawals between RIB dumps.

This pipeline uses **RIB dumps only**. Each RIB dump provides a self-contained, internally consistent snapshot of the routing table. This is deliberate: RIB dumps represent the converged state of the routing system at a point in time, whereas UPDATE files capture transient states that may include route flapping, convergence oscillations, and other noise.

### MRT Format

The raw data is in **MRT (Multi-Threaded Routing Toolkit)** binary format (RFC 6396), specifically the `TABLE_DUMP2` subtype for RIB entries. Each record contains:

| Field | Description | Example |
|-------|-------------|---------|
| Timestamp | When the dump was taken | `2025-11-17 00:00:00 UTC` |
| Peer IP/AS | The BGP peer that provided this route | `198.32.132.97` / AS 13335 |
| Prefix | The IP prefix being routed | `1.0.0.0/24` |
| AS_PATH | The sequence of ASes the route traverses | `3356 1299 13335` |
| Origin | How the route was learned (IGP/EGP/INCOMPLETE) | `IGP` |
| Communities | BGP community tags | `3356:100 3356:123` |

The **AS_PATH** attribute is the key field for topology construction. It lists the sequence of ASes a route advertisement has traversed, from the announcing AS back to the collector's peer. Each consecutive pair of ASes in the path represents a direct AS-to-AS link.

---

## 4. Pipeline Architecture

### Stage 1: Data Discovery and Download

```
RIPE RIS Broker API (or URL generation)
    |
    v
List of RIB dump URLs for [collector, date_range]
    |
    v  [urllib download with local caching]
Raw MRT .gz files in data/mrt_files/
```

The pipeline discovers available RIB files using the BGPKIT Broker API, which indexes all available MRT files across all RIPE RIS collectors. If the broker is unavailable, it falls back to constructing URLs directly from the known naming pattern (`bview.YYYYMMDD.HHMM.gz`).

Files are downloaded to a local cache directory. If a file already exists locally, the download is skipped.

### Stage 2: MRT Parsing

```
Raw MRT .gz files
    |
    v  [bgpkit.Parser — Rust-based MRT parser]
Structured TABLE_DUMP2 rows (14 columns)
    |
    v
Per-snapshot CSVs + combined CSV + parsing statistics
```

Each MRT file is parsed using `bgpkit-parser`, a Rust-based MRT parser with Python bindings (`pybgpkit`). It handles gzip decompression and binary MRT parsing transparently, producing structured records.

The parser extracts all 14 TABLE_DUMP2 fields into a CSV format. Withdrawal messages (type "W") are counted but excluded from row output since they indicate route removal, not active topology.

A **snapshot manifest** is produced that maps each snapshot ID to its timestamp, source URL, local file paths, and row count. This manifest drives all subsequent processing.

### Stage 3: Edge Extraction

```
Per-snapshot CSV (AS_PATH column)
    |
    v  [parse_as_path + extract_edges_from_as_path]
Edge set: {(ASN_a, ASN_b), ...} + edge occurrence counts
```

For each snapshot, the AS_PATH column is processed to extract AS-level topology edges:

1. **Tokenize** the space-separated AS_PATH string.
2. **Remove AS prepending**: Consecutive duplicate ASNs (e.g., `3356 3356 3356 1299`) are deduplicated to `3356 1299`. Prepending is a traffic engineering technique that does not represent additional links.
3. **Skip AS_SETs**: Tokens containing `{` or `}` (e.g., `{1234,5678}`) are skipped. AS_SETs represent route aggregation and don't encode clear adjacency relationships.
4. **Filter private/reserved ASNs**: ASNs in RFC 6996 private ranges (64512-65534, 4200000000-4294967294) and RFC 7300 reserved values (0, 23456, 65535, 4294967295) are excluded.
5. **Extract pairwise edges**: Each consecutive pair of valid ASNs in the deduplicated path produces a sorted edge tuple `(min, max)`.

Edge occurrence counts (how many routes contain each edge) are preserved as edge weights for the graph.

### Stage 4: Graph Construction

```
Edge set + edge counts
    |
    v  [NetworkX graph construction]
G_full (undirected weighted graph)
    |
    v  [LCC extraction]
G_lcc (Largest Connected Component)
    |
    v  [nx_to_nk conversion]
G_nk (NetworKit graph for fast computation)
```

An undirected, weighted NetworkX graph is constructed where:
- **Nodes** are Autonomous Systems (identified by ASN).
- **Edges** represent observed AS adjacencies, weighted by the number of routes that traverse each link.

The **Largest Connected Component (LCC)** is extracted because many graph features (diameter, algebraic connectivity, closeness centrality) are only defined for connected graphs. The LCC typically contains 99%+ of all nodes, with the remaining components being tiny fragments caused by incomplete routing visibility.

If NetworKit is available, the LCC is also converted to NetworKit's internal format. NetworKit uses contiguous integer node IDs (0, 1, 2, ...) rather than ASN-based IDs, so bidirectional mappings (`nx2nk_map`, `nk2nx_map`) are maintained.

### Stage 5: Feature Extraction

```
G_lcc + G_nk
    |
    v  [extract_graph_level_features]
16 graph-level features + shared_data (_bc_map, _core_map)
    |
    v  [extract_node_level_features]  (reuses shared_data)
10 node-level features per ASN
```

Features are extracted in two passes:

1. **Graph-level features** compute 16 structural properties of the entire topology (see `docs/feature_definitions.md` for full details). During this pass, betweenness centrality and k-core decomposition -- the two most expensive computations -- are computed once and stored in `shared_data` for reuse.

2. **Node-level features** compute 10 properties for every AS in the LCC, reusing the betweenness and k-core maps from the graph-level pass to avoid redundant computation.

Each feature computation is wrapped in `try/except` for graceful degradation: if one feature fails (e.g., eigenvalue solver doesn't converge), the pipeline continues with the remaining features.

### Stage 6: Accumulation and Export

```
Per-snapshot feature dicts/DataFrames
    |
    v  [concatenation + sorting]
graph_level_timeseries_*.csv  (one row per snapshot)
node_level_timeseries_*.csv   (one row per ASN per snapshot)
    |
    v  [visualization]
Time-series plots, degree distribution, centrality correlations
```

Results from all snapshots are combined into two time-series DataFrames, sorted by timestamp. The graph-level DataFrame has one row per snapshot; the node-level DataFrame has one row per (snapshot, ASN) pair. Both are exported as CSV files.

Per-snapshot graph features are also exported as individual JSON files for easy programmatic access. Visualization cells produce time-series plots for key graph features, the degree distribution (linear and log-log CCDF), and a Spearman correlation heatmap of centrality measures.

---

## 5. Performance Design

### The Scale Challenge

A single RIB dump from one collector contains approximately 10-15 million route entries. Parsing produces a CSV of ~1 GB. The resulting AS-level topology graph has approximately 70,000-80,000 nodes and 150,000-200,000 edges. Computing all 26 features on a graph this size requires careful attention to algorithmic complexity.

### Key Optimizations

**Sparse matrix computation.** The adjacency matrix $A$ and Laplacian matrix $L$ are computed once in `scipy.sparse` format at the start of graph-level extraction. These sparse matrices are reused across features 5, 6, 8-11, and 16, avoiding repeated dense matrix construction.

**Sparse eigensolvers.** Algebraic connectivity uses `scipy.sparse.linalg.eigsh` with `which='SM'` directly on the sparse Laplacian, rather than NetworkX's `nx.algebraic_connectivity()` which defaults to the `tracemin_pcg` method. This changes computation time from minutes to seconds on AS-level graphs. Similarly, spectral radius uses `eigsh` with `which='LM'` and `k=1`.

**Conditional full vs. partial spectrum.** For graphs with fewer than 5,000 nodes, the full eigenvalue spectrum is computed via dense eigendecomposition (enabling exact Kirchhoff index, spanning tree count, and symmetry ratio). For larger graphs, only 300 eigenvalues are computed via sparse `eigsh`, and features that require the full spectrum (log spanning trees) are set to null.

**Shared computation.** Betweenness centrality (the most expensive single feature at $O(VE)$ for exact computation) and k-core decomposition are computed once during graph-level extraction and passed to node-level extraction via `shared_data`. This halves the time for these two computations.

**NetworKit acceleration.** When available, NetworKit (C++-implemented graph algorithms) provides 10-100x speedups for clustering, diameter, betweenness, closeness, eigenvector centrality, PageRank, local clustering, core decomposition, and BFS-based eccentricity. The pipeline gracefully falls back to NetworkX when NetworKit is not installed.

**Sampled computation for expensive features.** Betweenness centrality uses $k=500$ pivot sampling (or NetworKit's `ApproxBetweenness` with $\epsilon=0.01$). Average path length for large graphs ($n \geq 20000$) is estimated by sampling 500 source nodes. Node clique number uses greedy approximation for graphs with $n > 5000$.

**Memory management.** Graph objects are explicitly deleted after each snapshot (`del G, G_lcc, G_nk, node_df`) to free memory before processing the next snapshot.

---

## 6. Output Schema

### Primary Outputs

**`graph_level_timeseries_{collector}_{start}_{end}.csv`**

One row per snapshot. Contains metadata columns (`snapshot_id`, `timestamp`, `collector`), graph size columns (`n_nodes`, `n_edges`, `n_nodes_full`, `n_edges_full`, `n_components`, `lcc_fraction`, `is_connected`), and all 16 graph-level feature columns. See `docs/feature_definitions.md` for the complete column reference.

**`node_level_timeseries_{collector}_{start}_{end}.csv`**

One row per (snapshot, ASN) pair. Contains `asn`, `snapshot_id`, `timestamp`, and all 10 node-level feature columns (`degree`, `degree_centrality`, `betweenness_centrality`, `closeness_centrality`, `eigenvector_centrality`, `pagerank`, `local_clustering`, `avg_neighbor_degree`, `node_clique_number`, `eccentricity`, `core_number`).

### Intermediate Outputs

| File | Description |
|------|-------------|
| `output/rib_parsed_*.csv` | Combined parsed RIB entries (all snapshots) |
| `output/parsing_stats.csv` | Per-file parsing statistics |
| `output/snapshot_manifest.csv` | Snapshot metadata mapping |
| `output/snapshot_errors.csv` | Error log for failed snapshots |
| `output/snapshots/rib_*.csv` | Per-snapshot parsed RIB entries |
| `output/snapshots/graph_features_*.json` | Per-snapshot graph features as JSON |

### Visualizations

| File | Description |
|------|-------------|
| `figures/graph_features_timeseries.png` | 5x2 grid of graph feature time-series |
| `figures/degree_distribution.png` | Degree histogram + log-log CCDF |
| `figures/centrality_correlations.png` | Spearman correlation heatmap of centrality measures |

---

## 7. Configuration

All pipeline parameters are configurable in Cell 5:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `COLLECTOR` | `rrc04` | RIPE RIS route collector ID |
| `START_DATE` | `2025-11-17` | Start of date range (inclusive) |
| `END_DATE` | `2025-11-18` | End of date range (inclusive) |
| `BETWEENNESS_SAMPLE_K` | `500` | Number of pivot nodes for sampled betweenness |
| `COMPUTE_SPECTRAL` | `True` | Whether to compute spectral features (8-11, 16) |
| `MAX_NODES_FOR_CLIQUE` | `5000` | Node threshold for exact vs. greedy clique computation |
| `PER_SNAPSHOT_CSV` | `True` | Save individual CSV per snapshot |

---

## 8. Dependencies

| Package | Purpose |
|---------|---------|
| `pybgpkit` | Rust-based MRT parser and BGPKIT Broker client |
| `networkx` | Primary graph library for construction and feature extraction |
| `scipy` | Sparse matrix operations, eigensolvers, statistics |
| `numpy` | Numerical operations |
| `pandas` | DataFrames for tabular data |
| `matplotlib` | Visualization |
| `networkit` | *Optional.* C++-based graph algorithms for performance-critical computations |

---

## 9. How This Fits into the Larger Project

This notebook is one stage of a multi-stage BGP anomaly detection pipeline:

1. **Feature Extraction** (this notebook): Transforms raw BGP data into structured graph features as time series.
2. **Anomaly Labeling** (`BGP_Anomaly_Label_Reinforcement_v2.ipynb`): Applies labeling strategies to identify known anomalous events in the time series.
3. **Label Validation** (`BGP_Label_Validation_Discovery_HDBSCAN.ipynb`): Uses unsupervised clustering (HDBSCAN) to validate and discover anomaly labels.
4. **Downstream Modeling**: The labeled time-series features feed into anomaly detection models (z-score, EWMA, autoencoders, etc.) that can flag novel routing events in real time.

The key design principle is treating each 8-hour RIB snapshot as an independent observation, producing a time series where standard anomaly detection methods can be applied directly. Graph-level features capture global structural changes (outages, large-scale hijacks), while node-level features capture per-AS behavioral changes (targeted hijacks, peering disputes, route leaks affecting specific ASes).
