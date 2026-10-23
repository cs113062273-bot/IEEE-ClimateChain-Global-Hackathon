// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title SeasonRecord
/// @notice The season's daily readings, posted by each designated provider, and the hot
/// spells the contract computes from them.
///
/// The climate statistics are fixed before the season: for every season day the signed
/// rule holds the "unusually hot" threshold (the calendar-day percentile of the agreed
/// 30-year normal), and the contract stores the fingerprint of each provider's list. A
/// provider posts readings day by day, in order, in thousandths of a degree, each marked
/// observed, filled (gap filled by the agreed method) or missing. The contract compares
/// every reading with the signed threshold and keeps the running hot spell, the longest
/// spell, and the filled and missing counts itself, so a provider cannot report a spell
/// its own readings do not show.
///
/// Days are append-only: a day already on chain cannot be changed, and a day that has
/// not ended yet cannot be posted. A spell already posted therefore only grows. Every
/// posted day is folded into `dayLog` (keccak over the previous log, the reading and its
/// status), so anyone can check the on-chain record against the raw data.
///
/// There is deliberately no commit-reveal: the readings are public data and the verdict
/// is arithmetic on them, so hiding them would not stop anyone predicting the result.
abstract contract SeasonRecord {
    enum Verdict {
        None,
        Met,
        NotMet,
        Abstain
    }

    uint8 internal constant OBSERVED = 0;
    uint8 internal constant FILLED = 1;
    uint8 internal constant MISSING = 2;

    struct Record {
        uint16 posted; // season days on chain, from the first day of the season
        uint16 run; // hot days in a row at the end of what is posted
        uint16 longest; // longest run of hot days so far
        uint16 filled;
        uint16 missing;
        bool isFinal; // the provider's last word: the whole season is posted
        uint64 updatedAt;
        bytes32 dayLog; // keccak chain over every posted (reading, status)
        bytes32 evidenceDigest; // sha256 of the provider's evidence for its latest post (names the fetched files)
    }

    mapping(uint256 => mapping(address => Record)) internal records;
    mapping(uint256 => uint256) public reportCount; // final posts

    event DaysPosted(
        uint256 indexed agreementId,
        address indexed provider,
        uint16 fromDay,
        uint16 count,
        uint16 longestSpell,
        uint16 filled,
        uint16 missing,
        bytes32 evidenceDigest,
        bool isFinal
    );

    error AlreadyReported();
    error EmptyEvidence();
    error BadDays();
    error BadStatus();
    error FutureDay();
    error IncompleteSeason();
    error NormalMismatch();
    error NoNormal();

    function getRecord(uint256 agreementId, address provider) external view returns (Record memory) {
        return records[agreementId][provider];
    }

    /// Appends `values`/`status` after the days already posted and updates the spell counts.
    function _append(Record storage r, int32[] calldata normal, int32[] calldata values, uint8[] calldata status) internal {
        uint256 day = r.posted;
        uint16 run = r.run;
        uint16 longest = r.longest;
        uint16 filled = r.filled;
        uint16 missing = r.missing;
        bytes32 log = r.dayLog;
        for (uint256 i = 0; i < values.length; i++) {
            uint8 s = status[i];
            int32 v = values[i];
            if (s > MISSING || (s == MISSING && v != 0)) revert BadStatus();
            if (s == MISSING) {
                missing++;
                run = 0;
            } else {
                if (s == FILLED) filled++;
                if (v > normal[day]) {
                    run++;
                    if (run > longest) longest = run;
                } else {
                    run = 0;
                }
            }
            log = keccak256(abi.encodePacked(log, v, s));
            day++;
        }
        r.posted = uint16(day);
        r.run = run;
        r.longest = longest;
        r.filled = filled;
        r.missing = missing;
        r.dayLog = log;
    }
}
