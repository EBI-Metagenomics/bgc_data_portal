# Staged-bundle column contract

`staged_columns.json` is a copy of `docs/staged_columns.json` from
[mgnify-bgcs-etl](https://github.com/EBI-Metagenomics/mgnify-bgcs-etl) at commit
`b3f4714`. The ETL keeps that file equal to what it writes;
`tests/unit/test_staged_columns_contract.py` checks that every column the
loader and `apply_taxonomy_mapping` read is in it.

When the ETL changes a staged column, re-copy the file here in the same portal
PR that adapts the loader, and update the commit above.
