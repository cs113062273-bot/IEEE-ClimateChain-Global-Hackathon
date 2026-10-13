import { executeRequest, errorResult, stringify, ChainError } from './chain.mjs';

let output, request;
try {
  let raw = '';
  for await (const chunk of process.stdin) {
    raw += chunk.toString('utf8');
    if (Buffer.byteLength(raw,'utf8') > 131072) throw new ChainError('INVALID_INPUT','Bridge input exceeds 128 KiB');
  }
  try { request = JSON.parse(raw); } catch { throw new ChainError('INVALID_INPUT','Bridge input must be valid JSON'); }
  output = await executeRequest(request);
} catch (error) { output = errorResult(error, request?.action ?? request?.operation); }
process.stdout.write(stringify(output)+'\n');
