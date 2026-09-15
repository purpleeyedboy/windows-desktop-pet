"""Fail-closed receipt assembler for IFileOperationProgressSink callbacks."""
from __future__ import annotations
from dataclasses import dataclass
from .business import TrustedRecycleReceipt


@dataclass
class ProgressSinkEvidence:
    operation_id: str
    expected_items: int = 1
    post_delete_count: int = 0
    post_delete_hresult: int | None = None
    newly_created_item_id: str | None = None
    source_volume_serial: int = 0
    source_file_id_128: bytes = b""

    def post_delete_item(self, operation_id: str, hresult: int, newly_created_item_id: str | None):
        if operation_id != self.operation_id:
            raise ValueError("ProgressSink OperationId mismatch")
        self.post_delete_count += 1
        self.post_delete_hresult = int(hresult)
        self.newly_created_item_id = newly_created_item_id

    def finish(self, perform_hresult: int, aborted: bool) -> TrustedRecycleReceipt:
        return TrustedRecycleReceipt(
            operation_id=self.operation_id,
            item_count=self.post_delete_count if self.post_delete_count == self.expected_items else 0,
            post_delete_hresult=(
                self.post_delete_hresult if self.post_delete_hresult is not None else -1
            ),
            newly_created_item_id=self.newly_created_item_id or "",
            perform_hresult=int(perform_hresult),
            aborted=bool(aborted),
            source_volume_serial=self.source_volume_serial,
            source_file_id_128=self.source_file_id_128,
        )
