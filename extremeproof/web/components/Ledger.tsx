"use client";
import type { TxInfo } from "@/lib/chain";

export interface LogEntry {
  date: string;
  text: string;
  tx?: TxInfo;
}

const short = (h: string) => `${h.slice(0, 10)}…${h.slice(-6)}`;

/** The event log, with the transaction behind each step read from its receipt. */
export function Ledger({ entries, contract, chainId }: { entries: LogEntry[]; contract?: string; chainId?: number }) {
  const txs = entries.filter((e) => e.tx);
  const gas = txs.reduce((n, e) => n + e.tx!.gas, 0);
  return (
    <>
      <ol className="log">
        {entries.map((l, i) => (
          <li key={i} data-tx={l.tx?.hash} data-block={l.tx?.block} data-gas={l.tx?.gas} data-events={l.tx?.events.join(",")}>
            <span className="t">{l.date}</span>
            <span>
              <span className="what">{l.text}</span>
              {l.tx && (
                <span className="tx" title={l.tx.hash}>
                  tx {short(l.tx.hash)} · block {l.tx.block} · {l.tx.gas.toLocaleString("en-US")} gas
                  {l.tx.events.length > 0 && <> · emits {l.tx.events.join(", ")}</>}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>
      {txs.length > 0 && (
        <p className="ledger-sum">
          <strong>{txs.length} transactions</strong>, {gas.toLocaleString("en-US")} gas in total{chainId ? ` on chain ${chainId}` : ""}
          {contract && <> · TriggerAgreement <code title={contract}>{short(contract)}</code></>}. Each line is read back from its receipt; checks and clock moves are not transactions.
        </p>
      )}
    </>
  );
}
