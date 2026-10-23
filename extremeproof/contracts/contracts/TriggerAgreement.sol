// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {SeasonRecord} from "./SeasonRecord.sol";

/// @title TriggerAgreement
/// @notice A pre-arranged relief payout whose trigger rule is fixed before the season starts.
///
/// Three parties must approve the same spec hash: the funder (who also deposits the
/// money), a representative of the people the money is for, and an independent checker.
/// Once all three have approved, nothing about the agreement can be changed; a different
/// rule needs a new agreement. Each designated data provider posts the season's daily
/// readings (see SeasonRecord); the contract compares them with the daily thresholds
/// signed before the season and computes the hot spells and each provider's verdict.
///
/// The payout follows a signed ladder (spell length -> share of the deposit). During the
/// season, as soon as a quorum of providers' posted readings show a spell reaching a rung,
/// anyone can release that share (`release`); money released is never taken back. After the season
/// the part of the payout that a quorum of providers supports is paid; the part a quorum
/// says is not owed is returned at once; only the difference between the providers is
/// contested. That difference, or everything if fewer than a quorum could give a verdict,
/// goes to a dispute that ends either by unanimous decision of the three parties or,
/// after a deadline, by the fallback they chose up front. A one-step ladder at 100 % is
/// the classic all-or-nothing trigger. No single party can decide the result.
///
/// The spec itself (index, base period, pinned history, where the season data will come
/// from, gap-filling rule, the daily thresholds) lives off-chain as canonical JSON; its
/// sha256 is stored here, with the keccak fingerprint of each provider's daily thresholds
/// and the agreed data limits. Season data cannot be pinned at signing: it does not exist yet.
contract TriggerAgreement is SeasonRecord {
    enum Status {
        None,
        Proposed,
        Locked,
        Disputed,
        Paid,
        Refunded,
        Cancelled
    }

    enum Fallback {
        Refund,
        Pay
    }

    struct Parties {
        address funder;
        address community; // signs on behalf of the people the payout is for
        address checker; // independent reviewer of the rule
        address beneficiary; // receives the payout
    }

    struct Timing {
        uint64 windowStart; // must lock before this
        uint64 windowEnd; // providers may report only after this
        uint64 reportDeadline; // reports after this are refused; silence then counts as absent
        uint64 disputeWindow; // seconds the parties have to settle a dispute unanimously
    }

    /// The agreed data limits; beyond them a provider's verdict is "too little data".
    struct Limits {
        uint16 seasonDays; // readings per provider: (windowEnd - windowStart) / 1 day
        uint16 maxMissing; // days with no reading and no agreed fill
        uint16 maxFilled; // days filled by the agreed gap-filling method
    }

    struct Agreement {
        bytes32 specHash;
        Parties parties;
        address token;
        uint256 amount;
        uint8 quorum;
        Fallback onDispute;
        Status status;
        uint8 approvals; // bit 0 funder, bit 1 community, bit 2 checker
        bool funded;
        Timing timing;
        uint64 disputeEndsAt;
        uint256 paidOut; // released to the beneficiary so far
        uint256 contested; // held for the dispute: the providers' difference
        Limits limits;
    }

    /// One rung of the payout ladder: a spell of at least `minDays` pays `bps` of the deposit.
    struct Rung {
        uint16 minDays;
        uint16 bps;
    }

    uint8 private constant ALL_SIGNED = 7;
    uint16 private constant FULL = 10000;
    uint256 private constant MAX_RUNGS = 8;

    uint256 public nextId = 1;
    mapping(uint256 => Agreement) private agreements;
    mapping(uint256 => address[]) private providerList;
    mapping(uint256 => Rung[]) private ladders;
    mapping(uint256 => mapping(address => bool)) public isProvider;
    /// keccak256(abi.encodePacked(int32[] daily thresholds)) of the provider's data source, as
    /// signed; zero when that source has no valid normal (too little base-period data).
    mapping(uint256 => mapping(address => bytes32)) public normalOf;
    mapping(uint256 => uint8) public disputeVotesPay;
    mapping(uint256 => uint8) public disputeVotesRefund;
    uint256 private guard = 1;

    event Proposed(
        uint256 indexed id,
        bytes32 indexed specHash,
        address indexed proposer,
        address funder,
        address community,
        address checker,
        address beneficiary,
        address token,
        uint256 amount,
        uint8 quorum,
        uint8 onDispute
    );
    event Approved(uint256 indexed id, address indexed signer, uint8 role);
    event Funded(uint256 indexed id, address indexed funder, uint256 amount);
    event Locked(uint256 indexed id, bytes32 specHash);
    event Cancelled(uint256 indexed id, address indexed by);
    event Disputed(uint256 indexed id, uint256 yes, uint256 no, uint256 abstained, uint256 disputeEndsAt);
    event DisputeVote(uint256 indexed id, address indexed signer, bool pay);
    /// Money released: `paid` to the beneficiary and `refunded` to the funder in this step.
    event Settled(uint256 indexed id, uint256 paid, uint256 refunded, uint8 how);

    error BadSpec();
    error BadParties();
    error BadProviders();
    error BadQuorum();
    error BadTiming();
    error BadAmount();
    error BadLadder();
    error NothingToRelease();
    error NotParty();
    error NotProvider();
    error WrongStatus(Status actual);
    error SpecMismatch();
    error AlreadyApproved();
    error TooLate();
    error TooEarly();
    error TransferFailed();
    error Reentrancy();

    // how a settlement happened, for the Settled event
    uint8 private constant BY_QUORUM = 0; // the part a quorum of providers supports
    uint8 private constant BY_UNANIMOUS_PARTIES = 1;
    uint8 private constant BY_FALLBACK = 2;
    uint8 private constant BY_INTERIM = 3; // released during the season

    modifier nonReentrant() {
        if (guard != 1) revert Reentrancy();
        guard = 2;
        _;
        guard = 1;
    }

    // ---------------------------------------------------------------- setup

    function propose(
        bytes32 specHash,
        Parties calldata p,
        address token,
        uint256 amount,
        address[] calldata providers,
        bytes32[] calldata normals,
        uint8 quorum,
        Fallback onDispute,
        Timing calldata t,
        Limits calldata limits,
        Rung[] calldata ladder
    ) external returns (uint256 id) {
        if (specHash == bytes32(0)) revert BadSpec();
        if (
            p.funder == address(0) || p.community == address(0) || p.checker == address(0)
                || p.beneficiary == address(0) || p.funder == p.community || p.funder == p.checker
                || p.community == p.checker
        ) revert BadParties();
        if (msg.sender != p.funder && msg.sender != p.community && msg.sender != p.checker) revert NotParty();
        // A token address without code would make every transfer a silent no-op.
        if (token.code.length == 0 || amount == 0) revert BadAmount();
        if (providers.length < 2 || normals.length != providers.length) revert BadProviders();
        // A strict majority: "met" and "not met" can never both reach quorum.
        if (quorum == 0 || quorum > providers.length || uint256(quorum) * 2 <= providers.length) revert BadQuorum();
        if (
            t.windowStart <= block.timestamp || t.windowEnd <= t.windowStart || t.reportDeadline <= t.windowEnd
                || t.disputeWindow == 0 || (t.windowEnd - t.windowStart) % 1 days != 0
                || limits.seasonDays != (t.windowEnd - t.windowStart) / 1 days
        ) revert BadTiming();
        // Rungs strictly increase in days and share, start above zero and end at the full deposit.
        if (ladder.length == 0 || ladder.length > MAX_RUNGS || ladder[ladder.length - 1].bps != FULL) revert BadLadder();
        for (uint256 i = 0; i < ladder.length; i++) {
            if (ladder[i].minDays == 0 || ladder[i].bps == 0) revert BadLadder();
            if (i > 0 && (ladder[i].minDays <= ladder[i - 1].minDays || ladder[i].bps <= ladder[i - 1].bps)) revert BadLadder();
        }

        id = nextId++;
        for (uint256 i = 0; i < providers.length; i++) {
            address a = providers[i];
            if (
                a == address(0) || isProvider[id][a] || a == p.funder || a == p.community || a == p.checker
                    || a == p.beneficiary
            ) revert BadProviders();
            isProvider[id][a] = true;
            normalOf[id][a] = normals[i];
            providerList[id].push(a);
        }
        Agreement storage ag = agreements[id];
        ag.specHash = specHash;
        ag.parties = p;
        ag.token = token;
        ag.amount = amount;
        ag.quorum = quorum;
        ag.onDispute = onDispute;
        ag.status = Status.Proposed;
        ag.timing = t;
        ag.limits = limits;
        for (uint256 i = 0; i < ladder.length; i++) {
            ladders[id].push(ladder[i]);
        }
        emit Proposed(
            id, specHash, msg.sender, p.funder, p.community, p.checker, p.beneficiary, token, amount, quorum, uint8(onDispute)
        );
    }

    /// @notice Approve exactly this spec. The funder's approval also deposits the payout.
    function approve(uint256 id, bytes32 specHash) external nonReentrant {
        Agreement storage ag = _status(id, Status.Proposed);
        if (specHash != ag.specHash) revert SpecMismatch();
        if (block.timestamp >= ag.timing.windowStart) revert TooLate();
        uint8 bit = _roleBit(ag, msg.sender);
        if (ag.approvals & bit != 0) revert AlreadyApproved();
        ag.approvals |= bit;
        emit Approved(id, msg.sender, bit);
        bool fund = bit == 1;
        if (fund) ag.funded = true;
        if (ag.approvals == ALL_SIGNED) {
            ag.status = Status.Locked;
            emit Locked(id, ag.specHash);
        }
        if (fund) {
            _pull(ag.token, msg.sender, ag.amount);
            emit Funded(id, msg.sender, ag.amount);
        }
    }

    /// @notice Any of the three parties can abandon an agreement that is not yet locked.
    function cancel(uint256 id) external nonReentrant {
        Agreement storage ag = _status(id, Status.Proposed);
        _roleBit(ag, msg.sender);
        ag.status = Status.Cancelled;
        emit Cancelled(id, msg.sender);
        if (ag.funded) {
            ag.funded = false;
            _push(ag.token, ag.parties.funder, ag.amount);
        }
    }

    // ---------------------------------------------------------------- provider reports

    /// @notice A designated provider posts the next season days: readings in thousandths of a
    /// degree and their status (0 observed, 1 filled, 2 missing), with its daily thresholds as
    /// signed and the sha256 of its evidence. During the season only days that have ended can
    /// be posted; after it, the final post completes the season. A provider whose source has
    /// no valid normal can only file an empty final post, which counts as "too little data".
    function postDays(
        uint256 id,
        int32[] calldata normal,
        int32[] calldata values,
        uint8[] calldata status,
        bytes32 evidenceDigest,
        bool isFinal
    ) external {
        Agreement storage ag = _status(id, Status.Locked);
        if (!isProvider[id][msg.sender]) revert NotProvider();
        Timing storage t = ag.timing;
        if (block.timestamp < (isFinal ? t.windowEnd : t.windowStart)) revert TooEarly();
        if (isFinal ? block.timestamp > t.reportDeadline : block.timestamp >= t.windowEnd) revert TooLate();
        if (evidenceDigest == bytes32(0)) revert EmptyEvidence();
        bytes32 signed = normalOf[id][msg.sender];
        Record storage r = records[id][msg.sender];
        uint16 from = r.posted;
        if (signed == bytes32(0)) {
            if (!isFinal || values.length != 0) revert NoNormal();
        } else {
            // The thresholds are checked first: a provider cannot move the normal it was signed to.
            if (normal.length != ag.limits.seasonDays || keccak256(abi.encodePacked(normal)) != signed) revert NormalMismatch();
            if (r.isFinal) revert AlreadyReported();
            if (values.length != status.length || (!isFinal && values.length == 0)) revert BadDays();
            uint256 end = from + values.length;
            uint256 ended = (block.timestamp - t.windowStart) / 1 days; // season days that have ended
            if (end > ended || end > ag.limits.seasonDays) revert FutureDay();
            if (isFinal && end != ag.limits.seasonDays) revert IncompleteSeason();
            _append(r, normal, values, status);
        }
        if (r.isFinal) revert AlreadyReported();
        r.isFinal = isFinal;
        r.evidenceDigest = evidenceDigest;
        r.updatedAt = uint64(block.timestamp);
        if (isFinal) reportCount[id] += 1;
        emit DaysPosted(id, msg.sender, from, uint16(values.length), r.longest, r.filled, r.missing, evidenceDigest, isFinal);
    }

    /// @notice What a provider's posted readings say, computed here from its record.
    /// After the final post: "met" or "not met" by the longest spell, or "abstain" if the
    /// agreed data limits were exceeded or its source has no valid normal. During the season
    /// (or if it never filed a final post): "met" once a spell reaching the first rung is on
    /// chain and the limits can no longer be exceeded by the rest of the season; else nothing.
    function reportOf(uint256 id, address provider) public view returns (Verdict verdict, uint16 longestSpell) {
        Record storage r = records[id][provider];
        Limits storage l = agreements[id].limits;
        uint16 first = ladders[id][0].minDays;
        if (r.isFinal) {
            if (normalOf[id][provider] == bytes32(0) || r.missing > l.maxMissing || r.filled > l.maxFilled) {
                return (Verdict.Abstain, 0);
            }
            return (r.longest >= first ? Verdict.Met : Verdict.NotMet, r.longest);
        }
        if (
            r.posted > 0 && r.longest >= first && r.missing <= l.maxMissing
                && uint256(r.filled) + (l.seasonDays - r.posted) <= l.maxFilled
        ) return (Verdict.Met, r.longest);
        return (Verdict.None, 0);
    }

    /// @notice During the season anyone may release the share a quorum of providers already supports.
    function release(uint256 id) external nonReentrant {
        Agreement storage ag = _status(id, Status.Locked);
        (uint256 supported,,,,) = _supported(id, ag);
        if (supported <= ag.paidOut) revert NothingToRelease();
        uint256 delta = supported - ag.paidOut;
        ag.paidOut = supported;
        emit Settled(id, delta, 0, BY_INTERIM);
        _push(ag.token, ag.parties.beneficiary, delta);
    }

    /// @notice Anyone may finalize once every provider has reported or the report deadline has passed.
    /// Pays the share a quorum of providers supports, returns the share a quorum says is not
    /// owed, and sends only the difference (or everything, without a quorum of verdicts) to dispute.
    function finalize(uint256 id) external nonReentrant {
        Agreement storage ag = _status(id, Status.Locked);
        if (reportCount[id] < providerList[id].length && block.timestamp <= ag.timing.reportDeadline) revert TooEarly();
        (uint256 payNow, uint256 owedAtMost, uint256 yes, uint256 no, uint256 abstained) = _supported(id, ag);
        // Money released during the season stays released.
        uint256 released = ag.paidOut;
        if (payNow < released) payNow = released;
        if (owedAtMost < payNow) owedAtMost = payNow;
        uint256 refundNow = ag.amount - owedAtMost;
        ag.contested = owedAtMost - payNow;
        ag.paidOut = payNow;
        if (ag.contested == 0) {
            ag.status = payNow > 0 ? Status.Paid : Status.Refunded;
            ag.funded = false;
        } else {
            ag.status = Status.Disputed;
            ag.disputeEndsAt = uint64(block.timestamp) + ag.timing.disputeWindow;
            emit Disputed(id, yes, no, abstained, ag.disputeEndsAt);
        }
        uint256 payDelta = payNow - released;
        if (payDelta > 0 || refundNow > 0) emit Settled(id, payDelta, refundNow, BY_QUORUM);
        if (payDelta > 0) _push(ag.token, ag.parties.beneficiary, payDelta);
        if (refundNow > 0) _push(ag.token, ag.parties.funder, refundNow);
    }

    /// The share at least `quorum` providers support (paid) and the most at least `quorum`
    /// providers allow (anything above it is returned), from the current reports.
    function _supported(uint256 id, Agreement storage ag)
        private
        view
        returns (uint256 payNow, uint256 owedAtMost, uint256 yes, uint256 no, uint256 abstained)
    {
        address[] storage ps = providerList[id];
        uint16[] memory spells = new uint16[](ps.length);
        uint256 n;
        for (uint256 i = 0; i < ps.length; i++) {
            (Verdict v, uint16 spell) = reportOf(id, ps[i]);
            if (v == Verdict.Met || v == Verdict.NotMet) {
                if (v == Verdict.Met) yes++;
                else no++;
                // insertion sort, ascending; at most a handful of providers
                uint256 j = n++;
                while (j > 0 && spells[j - 1] > spell) {
                    spells[j] = spells[j - 1];
                    j--;
                }
                spells[j] = spell;
            } else if (v == Verdict.Abstain) {
                abstained++;
            }
        }
        owedAtMost = ag.amount; // without a quorum of verdicts nothing is agreed either way
        if (n >= ag.quorum) {
            // At least `quorum` providers measured a spell this long or longer ...
            payNow = _share(id, spells[n - ag.quorum], ag.amount);
            // ... and at least `quorum` measured one this short or shorter.
            owedAtMost = _share(id, spells[ag.quorum - 1], ag.amount);
        }
    }

    /// @notice The share of `amount` the signed ladder pays for a spell of `spell` days.
    function payoutFor(uint256 id, uint16 spell) public view returns (uint256 bps) {
        Rung[] storage l = ladders[id];
        for (uint256 i = 0; i < l.length && spell >= l[i].minDays; i++) {
            bps = l[i].bps;
        }
    }

    function _share(uint256 id, uint16 spell, uint256 amount) private view returns (uint256) {
        return amount * payoutFor(id, spell) / FULL;
    }

    // ---------------------------------------------------------------- disputes

    /// @notice During a dispute the three parties may settle, but only unanimously.
    function voteDispute(uint256 id, bool pay) external nonReentrant {
        Agreement storage ag = _status(id, Status.Disputed);
        uint8 bit = _roleBit(ag, msg.sender);
        if (pay) {
            disputeVotesPay[id] |= bit;
            disputeVotesRefund[id] &= ~bit;
        } else {
            disputeVotesRefund[id] |= bit;
            disputeVotesPay[id] &= ~bit;
        }
        emit DisputeVote(id, msg.sender, pay);
        if (disputeVotesPay[id] == ALL_SIGNED) _settle(id, ag, true, BY_UNANIMOUS_PARTIES);
        else if (disputeVotesRefund[id] == ALL_SIGNED) _settle(id, ag, false, BY_UNANIMOUS_PARTIES);
    }

    /// @notice After the dispute window anyone may apply the fallback chosen at signing.
    function settleDisputeByDefault(uint256 id) external nonReentrant {
        Agreement storage ag = _status(id, Status.Disputed);
        if (block.timestamp < ag.disputeEndsAt) revert TooEarly();
        _settle(id, ag, ag.onDispute == Fallback.Pay, BY_FALLBACK);
    }

    // ---------------------------------------------------------------- views

    function getAgreement(uint256 id) external view returns (Agreement memory) {
        return agreements[id];
    }

    function providersOf(uint256 id) external view returns (address[] memory) {
        return providerList[id];
    }

    function ladderOf(uint256 id) external view returns (Rung[] memory) {
        return ladders[id];
    }

    // ---------------------------------------------------------------- internals

    function _status(uint256 id, Status want) private view returns (Agreement storage ag) {
        ag = agreements[id];
        if (ag.status != want) revert WrongStatus(ag.status);
    }

    function _roleBit(Agreement storage ag, address who) private view returns (uint8) {
        if (who == ag.parties.funder) return 1;
        if (who == ag.parties.community) return 2;
        if (who == ag.parties.checker) return 4;
        revert NotParty();
    }

    /// Resolves the contested part of a dispute: to the beneficiary (`pay`) or back to the funder.
    function _settle(uint256 id, Agreement storage ag, bool pay, uint8 how) private {
        uint256 c = ag.contested;
        ag.contested = 0;
        if (pay) ag.paidOut += c;
        ag.status = ag.paidOut > 0 ? Status.Paid : Status.Refunded;
        ag.funded = false;
        emit Settled(id, pay ? c : 0, pay ? 0 : c, how);
        _push(ag.token, pay ? ag.parties.beneficiary : ag.parties.funder, c);
    }

    function _pull(address token, address from, uint256 amount) private {
        (bool ok, bytes memory ret) =
            token.call(abi.encodeWithSelector(0x23b872dd, from, address(this), amount)); // transferFrom
        if (!ok || (ret.length != 0 && !abi.decode(ret, (bool)))) revert TransferFailed();
    }

    function _push(address token, address to, uint256 amount) private {
        (bool ok, bytes memory ret) = token.call(abi.encodeWithSelector(0xa9059cbb, to, amount)); // transfer
        if (!ok || (ret.length != 0 && !abi.decode(ret, (bool)))) revert TransferFailed();
    }
}
