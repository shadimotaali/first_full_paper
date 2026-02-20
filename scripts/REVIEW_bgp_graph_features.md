# Code Review: `scripts/bgp_graph_features.ipynb`

## Summary

Reviewed the BGP AS-Level Topology Graph Feature Extraction Pipeline notebook from the `main` branch.
Found **7 logical issues**, **3 redundancies**, and **3 code quality issues**.

---

## Critical Logical Issues

### 1. Withdrawals treated as announcements in `parse_mrt_file` (Cell 9)

**Location:** `parse_mrt_file()`, line processing loop

The function extracts AS_PATH edges from ALL MRT elements regardless of `elem_type`.
In `rib_and_updates` mode, withdrawal messages ("W") from UPDATE files could contribute
edges to the graph. A withdrawal means a route is being *removed* -- its edges should not
be added to the topology. In practice, most MRT withdrawal messages lack AS_PATH so
this rarely produces wrong edges, but there is no guard against it.

**Fix:** Skip edge extraction for withdrawal elements:
```python
if elem.as_path and elem.elem_type != "W":
    as_path = parse_as_path(elem.as_path)
    ...
```

### 2. `rib_and_updates` mode produces a "super-graph" that never existed (Cell 10)

**Location:** Cell 10, edge merging logic

When `MODE = "rib_and_updates"`, edges from ALL RIB dumps AND all UPDATE files are merged
into a single `all_edges` set. This creates a topology where every edge ever observed during
the time window is present simultaneously. This graph never existed at any point in time --
it conflates steady-state topology with transient routing events (convergence, flapping,
brief route leaks).

Problems:
- Inflates edge counts with ephemeral edges
- Loses all temporal information from the UPDATE stream
- Resulting graph features don't represent any real routing state
- Withdrawals don't remove edges (they only add)

**Fix:** Either remove `rib_and_updates` mode or implement proper sequential UPDATE application
(start from RIB baseline, apply announcements/withdrawals in timestamp order).

### 3. Symmetry ratio meaningless with partial spectrum (Cell 25)

**Location:** Cell 25, symmetry ratio computation

Symmetry ratio = `|distinct eigenvalues of A| / (D + 1)` requires the FULL adjacency spectrum.
When `use_full_spectrum = False`, only 300 eigenvalues are computed out of potentially 70,000+.
The code computes `distinct_eigs` from only those 300 values, producing a severely
underestimated and meaningless result that is stored without qualification.

Additionally, the `if use_full_spectrum` / `else` branches contain identical code:
```python
distinct_eigs = len(np.unique(np.round(adjacency_eigs, 8)))
```

**Fix:** Either skip symmetry ratio when using partial spectrum, or clearly mark it as
approximate with a different feature name (e.g., `symmetry_ratio_approx`).

### 4. Natural connectivity uses wrong denominator for partial spectrum (Cell 25)

**Location:** Cell 25, natural connectivity computation

Natural connectivity = `ln[(1/n) * SUM exp(lambda_i)]` where sum is over all n eigenvalues.
The code uses `np.mean(np.exp(...))` which divides by `len(adjacency_eigs)` (300 for partial
spectrum) instead of `n_nodes`. This overestimates natural connectivity.

**Fix:** For partial spectrum:
```python
graph_features['natural_connectivity'] = float(
    max_eig + np.log(np.sum(np.exp(adjacency_eigs - max_eig)) / n_nodes)
)
```

### 5. No filtering of bogus/private ASNs (Cell 9)

**Location:** `parse_as_path()` and `parse_mrt_file()`

Private AS numbers (64512-65534 for 16-bit, 4200000000-4294967294 for 32-bit), reserved
ASNs (AS0, AS23456/AS_TRANS), and documentation ASNs (64496-64511, 65536-65551) are not
filtered. These appear as nodes in the graph and distort topology metrics.

**Fix:** Add ASN filtering:
```python
PRIVATE_ASN_RANGES = [
    (0, 0),            # Reserved
    (23456, 23456),    # AS_TRANS
    (64496, 64511),    # Documentation (16-bit)
    (64512, 65534),    # Private (16-bit)
    (65535, 65535),     # Reserved
    (65536, 65551),    # Documentation (32-bit)
    (4200000000, 4294967294),  # Private (32-bit)
    (4294967295, 4294967295),  # Reserved
]

def is_valid_asn(asn: int) -> bool:
    for lo, hi in PRIVATE_ASN_RANGES:
        if lo <= asn <= hi:
            return False
    return True
```

---

## Redundancies

### 6. Betweenness centrality computed twice (Cell 28 + Cell 34)

Betweenness centrality is computed in Cell 28 for graph-level statistics (mean, max, std,
skewness) and again in Cell 34 for per-node values. When using NetworKit's
`ApproxBetweenness`, these are two independent random approximations, so the graph-level
statistics from Cell 28 may not match the per-node values from Cell 34.

**Fix:** Remove the Cell 28 computation. Compute betweenness once in Cell 34, then derive
graph-level statistics from those per-node values.

### 7. k-Core decomposition computed twice (Cell 29 + Cell 42)

`CoreDecomposition` / `nx.core_number` runs in Cell 29 (graph-level metrics) and again in
Cell 42 (node-level core numbers). Pure duplication.

**Fix:** Compute core numbers once, reuse for both graph-level and node-level features.

### 8. Adjacency/Laplacian matrices recomputed (Cells 22, 23, 25)

- Cell 22: `nx.laplacian_matrix(G_lcc)` for algebraic connectivity
- Cell 23: `nx.adjacency_matrix(G_lcc)` for spectral radius
- Cell 25: Both matrices computed again

**Fix:** Compute once at the start of the feature extraction section, reuse everywhere.

---

## Code Quality Issues

### 9. `collect_metadata` parameter is dead code (Cell 9)

`parse_mrt_file()` accepts `collect_metadata` but never uses it -- metadata is always
collected regardless. Remove the parameter.

### 10. Eccentricity mostly NaN for large graphs (Cell 41)

When `n_nodes >= 30000`, eccentricity is sampled for only 200 nodes. The remaining ~69,800
nodes get NaN, making this feature unusable for downstream ML. Either compute for all nodes
(using NetworKit's more efficient algorithms) or remove the feature for large graphs.

### 11. Node clique number mostly NaN for large graphs (Cell 40)

Same issue -- for graphs larger than `MAX_NODES_FOR_CLIQUE` (5000), only innermost k-core
nodes get values. Consider removing this feature entirely for AS-level graphs since it's
NP-hard and the partial computation is not meaningful.

### 12. Edge weights not tracked

The graph is unweighted. When the same AS adjacency appears in thousands of AS_PATHs, no
frequency/weight is recorded. Edge frequency is informative for anomaly detection -- a
rarely-seen edge is more suspicious than a well-established one.

### 13. `generate_rib_urls` has dead boundary check (Cell 7)

The condition `if ts < start` can never be true within the loop structure since `current`
starts at `start` and only increments forward. This is dead code.

---

## RIB vs UPDATE Files: Recommendation

### Use RIB files only for graph feature extraction

| Aspect | RIB Files | UPDATE Files |
|--------|-----------|--------------|
| Content | Complete routing table snapshot | Incremental changes (announce/withdraw) |
| Frequency | Every 8 hours | Every 5 minutes |
| Self-contained | Yes | No (requires baseline state) |
| Use case | Static topology at time T | Dynamic behavior between snapshots |

**For graph-feature-based anomaly detection (this notebook's purpose): use RIB files only.**

Each RIB dump produces one complete graph snapshot. Multiple RIB dumps over time produce a
time series of graph features. This is the standard approach in the literature (Sanchez et al.,
Big-DAMA '19; Al-Musawi et al., 2017).

**UPDATE files should be used separately** for temporal/dynamic features:
- Volume of announcements/withdrawals per time interval
- Rate of new edge appearance/disappearance
- AS_PATH instability metrics
- Prefix-level churn rates

These are complementary to graph-level features and should be extracted in a separate pipeline,
not merged into the graph construction.

**The current `rib_and_updates` mode is methodologically incorrect** and should be removed
or replaced with proper sequential state tracking.
