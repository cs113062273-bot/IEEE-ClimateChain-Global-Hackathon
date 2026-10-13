// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice Integrity registry for modeled evidence; does not certify meters or credits.
/// @dev Uniqueness covers exact site/time/category tuples, not overlapping periods.
contract GridProofRegistry {
    enum Status { None, Active, Revoked }

    struct Record {
        bytes32 claimKey;
        bytes32 digest;
        address submitter;
        uint64 createdAt;
        Status status;
        uint256 previousRecordId;
        uint256 replacedByRecordId;
        bytes32 reasonDigest;
        uint64 revokedAt;
    }

    uint256 public nextRecordId = 1;
    mapping(bytes32 => uint256) public latestRecordForScope;
    mapping(uint256 => Record) private records;

    error InvalidScope();
    error ZeroDigest();
    error DuplicateActiveClaim(bytes32 claimKey);
    error ReplacementRequired(bytes32 claimKey);
    error UnknownClaim(bytes32 claimKey);
    error Unauthorized(address caller);
    error ClaimNotActive(bytes32 claimKey);
    error RevokeBeforeReplace(bytes32 claimKey);

    event ClaimRegistered(
        bytes32 indexed claimKey, uint256 indexed recordId, address indexed submitter,
        bytes32 digest, uint64 createdAt, uint256 previousRecordId
    );
    event ClaimRevoked(
        bytes32 indexed claimKey, uint256 indexed recordId, address indexed submitter,
        bytes32 reasonDigest, uint64 revokedAt
    );
    event ClaimReplaced(
        bytes32 indexed claimKey, uint256 indexed previousRecordId, uint256 indexed recordId,
        bytes32 previousDigest, bytes32 replacementDigest
    );

    function computeClaimKey(
        bytes32 siteHash, uint64 fromUtc, uint64 toUtc, bytes32 categoryHash
    ) public pure returns (bytes32) {
        if (siteHash == bytes32(0) || categoryHash == bytes32(0) || fromUtc >= toUtc) {
            revert InvalidScope();
        }
        return keccak256(abi.encode(siteHash, fromUtc, toUtc, categoryHash));
    }

    function registerClaim(
        bytes32 siteHash, uint64 fromUtc, uint64 toUtc, bytes32 categoryHash, bytes32 digest
    ) external returns (bytes32 claimKey, uint256 recordId) {
        if (digest == bytes32(0)) revert ZeroDigest();
        claimKey = computeClaimKey(siteHash, fromUtc, toUtc, categoryHash);
        uint256 previous = latestRecordForScope[claimKey];
        if (previous != 0) {
            if (records[previous].status == Status.Active) revert DuplicateActiveClaim(claimKey);
            revert ReplacementRequired(claimKey);
        }
        recordId = createRecord(claimKey, digest, 0);
    }

    function revokeClaim(bytes32 claimKey, bytes32 reasonDigest) external {
        if (reasonDigest == bytes32(0)) revert ZeroDigest();
        uint256 recordId = latestRecordForScope[claimKey];
        if (recordId == 0) revert UnknownClaim(claimKey);
        Record storage record = records[recordId];
        if (msg.sender != record.submitter) revert Unauthorized(msg.sender);
        if (record.status != Status.Active) revert ClaimNotActive(claimKey);
        record.status = Status.Revoked;
        record.reasonDigest = reasonDigest;
        record.revokedAt = uint64(block.timestamp);
        emit ClaimRevoked(claimKey, recordId, msg.sender, reasonDigest, record.revokedAt);
    }

    function replaceClaim(bytes32 claimKey, bytes32 digest) external returns (uint256 recordId) {
        if (digest == bytes32(0)) revert ZeroDigest();
        uint256 previous = latestRecordForScope[claimKey];
        if (previous == 0) revert UnknownClaim(claimKey);
        Record storage record = records[previous];
        if (msg.sender != record.submitter) revert Unauthorized(msg.sender);
        if (record.status != Status.Revoked) revert RevokeBeforeReplace(claimKey);
        recordId = createRecord(claimKey, digest, previous);
        record.replacedByRecordId = recordId;
        emit ClaimReplaced(claimKey, previous, recordId, record.digest, digest);
    }

    function getClaim(bytes32 claimKey) external view returns (Record memory) {
        return records[latestRecordForScope[claimKey]];
    }

    function getRecord(uint256 recordId) external view returns (Record memory) {
        return records[recordId];
    }

    function verifyClaim(bytes32 claimKey, bytes32 expectedDigest)
        external view returns (bool matches, Status status, bytes32 digest, uint256 recordId)
    {
        recordId = latestRecordForScope[claimKey];
        Record storage record = records[recordId];
        status = record.status;
        digest = record.digest;
        matches = status == Status.Active && expectedDigest != bytes32(0) && digest == expectedDigest;
    }

    function createRecord(bytes32 claimKey, bytes32 digest, uint256 previous)
        private returns (uint256 recordId)
    {
        recordId = nextRecordId++;
        records[recordId] = Record({
            claimKey: claimKey, digest: digest, submitter: msg.sender,
            createdAt: uint64(block.timestamp), status: Status.Active,
            previousRecordId: previous, replacedByRecordId: 0,
            reasonDigest: bytes32(0), revokedAt: 0
        });
        latestRecordForScope[claimKey] = recordId;
        emit ClaimRegistered(claimKey, recordId, msg.sender, digest, uint64(block.timestamp), previous);
    }
}
