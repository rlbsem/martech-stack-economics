# Preserved clock-calibration observations

These are exploratory local HTTP observations, **not source-committed release acceptance**. The six-second and eighteen-second clock profiles failed to deliver the full surge within the scaled freshness deadlines. Neither failure was overwritten or called a saving.

- Six-second profile: 27,200 / 56,700 records on time; 29,500 unresolved; synthetic observed cost 546 cents versus predicted 782. The separate normal trial delivered all 5,400 records at 518 cents.
- Eighteen-second profile: 37,450 / 56,700 records on time; 19,250 unresolved; synthetic observed cost 628 cents versus predicted 782. A request arrival after a source deadline remained visible.

The development worktree was modified. The first summary's `source_commit` identifies the then-current repository HEAD, not a clean implementation checkpoint. Its separately collected `source-fingerprints.json` records the materialized source hashes captured by the preceding verification. The eighteen-second probe did not capture a complete source manifest. Their original raw observations and results are retained without claiming exact reproducibility from a clean commit.

The qualified suite uses an explicitly declared 36-second profile and source-bound records. Its six-second scaled deadline for time-sensitive workflows is a local test envelope; it does not change the original ten-minute business requirement or establish production capacity. See the current acceptance entry point for actual results.
