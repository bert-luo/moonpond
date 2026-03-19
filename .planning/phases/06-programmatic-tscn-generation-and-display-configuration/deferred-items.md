# Deferred Items

## Pre-existing: test_contract_generator.py mock needs type="text" on content blocks

- **File:** backend/backend/tests/test_contract_generator.py
- **Issue:** `_make_mock_client()` uses `MagicMock(text=text)` for content blocks but does not set `type="text"`. The contract_generator now filters by `block.type == "text"` (for thinking mode support), causing the mock to fail.
- **Fix:** Set `block.type = "text"` on the mock content block in `_make_mock_client()`, same pattern used in the fix applied to test_contract_pipeline.py.
- **Discovered during:** 06-02 Task 2 verification
