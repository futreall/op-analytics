"""Block Batching Utilities

We split ingestion into batches to meet the following goals:

  - Incremental ingestion of raw onchain data by block number.
  - Integration with BigQuery using a hive partitioned BigQuery external table.

Given a range of block numbers we want to have a deterministic way of locating where the
data for those blocks is stored in GCS.
"""

from dataclasses import dataclass

from op_coreutils.logger import structlog

from op_datasets.utils.blockrange import BlockRange

log = structlog.get_logger()


# For each chain we configure the block batch size that should be used. The batch size
# can change over time for a chain, so the configuration stores the block numbers at
# which the batch size changes. We refer to these block numbers as "delimiters".
#
# At the start of the chain or for some smaller chains we can use very large batches.
# For chains that grow in usage we have to use progressively smaller batches.


@dataclass
class Delimiter:
    block_number: int
    batch_size: int

    @property
    def next_block(self):
        return self.block_number + self.batch_size


MICROBATCH_SIZE_CONFIGURATION = {
    # Non-default
    "base": [
        Delimiter(block_number=0, batch_size=10000),
        Delimiter(block_number=10000000, batch_size=5000),
        Delimiter(block_number=15000000, batch_size=2000),
        Delimiter(block_number=20900000, batch_size=1000),
    ],
    "op": [
        Delimiter(block_number=0, batch_size=10000),
        Delimiter(block_number=62000000, batch_size=5000),
        Delimiter(block_number=94000000, batch_size=2000),
    ],
    # Default
    "automata": [Delimiter(0, 20000)],
    "bob": [Delimiter(0, 20000)],
    "cyber": [Delimiter(0, 20000)],
    "fraxtal": [Delimiter(0, 20000)],
    "ham": [Delimiter(0, 20000)],
    "kroma": [Delimiter(0, 20000)],
    "lisk": [Delimiter(0, 20000)],
    "lyra": [Delimiter(0, 20000)],
    "metal": [Delimiter(0, 20000)],
    "mint": [Delimiter(0, 20000)],
    "mode": [Delimiter(0, 20000)],
    "orderly": [Delimiter(0, 20000)],
    "polynomial": [Delimiter(0, 20000)],
    "race": [Delimiter(0, 20000)],
    "redstone": [Delimiter(0, 20000)],
    "shape": [Delimiter(0, 20000)],
    "swan": [Delimiter(0, 20000)],
    "xterio": [Delimiter(0, 20000)],
    "zora": [Delimiter(0, 20000)],
    "worldchain": [Delimiter(0, 20000)],
}


class InvalidMicrobatchConfig(Exception):
    pass


def validate_microbatch_configuration(boundaries: list[Delimiter]):
    for i, boundary in enumerate(boundaries):
        if i == 0:
            if boundary.block_number != 0:
                raise InvalidMicrobatchConfig(
                    f"the first delimiter should always start at block 0: {boundary}"
                )

        else:
            prev_boundary = boundaries[i - 1]
            distance = boundary.block_number - prev_boundary.block_number
            if distance % prev_boundary.batch_size != 0:
                raise InvalidMicrobatchConfig(
                    f"delimiter block number should align: {prev_boundary} -> {boundary}"
                )


for config in MICROBATCH_SIZE_CONFIGURATION.values():
    validate_microbatch_configuration(config)


def find_batch_delimiter(boundaries: list[Delimiter], block_number: int) -> Delimiter:
    padded_start_boundaries = [boundaries[0]] + boundaries
    padded_end_boundaries = boundaries + [boundaries[-1]]

    for prev_delimiter, delimiter in zip(padded_start_boundaries, padded_end_boundaries):
        assert delimiter.block_number % delimiter.batch_size == 0

        if delimiter.block_number <= block_number:
            continue
        else:
            break

    return Delimiter(
        block_number=block_number - (block_number % prev_delimiter.batch_size),
        batch_size=prev_delimiter.batch_size,
    )


@dataclass
class BlockBatch:
    """Represents a single processing batch.

    BlockBatch is structurally the same as a BlockRange, but the BlockBatch is
    constructed to match the block bach boundaries configured for each chain."""

    chain: str
    min: int  # inclusive
    max: int  # exclusive

    @property
    def contextvars(self):
        return dict(
            chain=self.chain,
            blocks=f"#{self.min}-{self.max}",
        )

    def __len__(self):
        return self.max - self.min

    def num_blocks(self):
        return self.max - self.min

    def filter(self, number_column: str = "number"):
        return f" {number_column} >= {self.min} and {number_column} < {self.max}"

    def construct_filename(self):
        return f"{self.min:012d}"

    def construct_dataset_path(self):
        return f"chain={self}"

    def construct_date_path(self, dt: str):
        return f"chain={self.chain}/dt={dt}"

    def construct_parquet_path(self, dt: str):
        return f"chain={self.chain}/dt={dt}/{self.construct_filename()}.parquet"

    def construct_parquet_filename(self):
        return f"{self.construct_filename()}.parquet"

    def construct_marker_path(self):
        return f"chain={self.chain}/{self.construct_filename()}.json"


def split_block_range(chain: str, block_range: BlockRange) -> list[BlockBatch]:
    boundaries = MICROBATCH_SIZE_CONFIGURATION[chain]
    return split_block_range_from_boundaries(chain, boundaries, block_range)


def split_block_range_from_boundaries(
    chain: str,
    boundaries: list[Delimiter],
    block_range: BlockRange,
) -> list[BlockBatch]:
    validate_microbatch_configuration(boundaries)

    delimiter = find_batch_delimiter(boundaries, block_range.min)

    batches: list[BlockBatch] = []
    while delimiter.block_number < block_range.max:
        new_delimiter = find_batch_delimiter(boundaries, delimiter.next_block)
        if delimiter.next_block != new_delimiter.block_number:
            raise ValueError(f"inconsisent batch: {delimiter}  ..  {new_delimiter}")
        batches.append(BlockBatch(chain, delimiter.block_number, delimiter.next_block))
        delimiter = new_delimiter
    return batches
