// This module prepares configuration only. It never broadcasts or exposes a signer to the public bridge.
import { privateKeyToAccount } from 'viem/accounts';
import { ChainError } from './chain.mjs';

export function readSepoliaSigner(environment=process.env) {
  const secret=environment.GRIDPROOF_SEPOLIA_PRIVATE_KEY;
  if (!secret || !/^0x[0-9a-fA-F]{64}$/.test(secret)) throw new ChainError('SIGNER_NOT_CONFIGURED','Provide a dedicated test-only signer through the operator environment; never via JSON/API/browser configuration');
  try {return privateKeyToAccount(secret);} catch {throw new ChainError('INVALID_SIGNER','Signer secret is invalid');}
}

export function publicSigningIsDisabled() {
  throw new ChainError('AUTHORIZATION_REQUIRED','No Sepolia deployment or broadcast is implemented in this preparation command; an explicit authorized deployment step is required');
}
