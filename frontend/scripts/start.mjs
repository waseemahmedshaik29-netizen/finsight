// Keep the local terminal bound to loopback. Docker runs its own server entrypoint.
process.env.HOSTNAME = process.env.FINSIGHT_HOST || '127.0.0.1';
await import('../.next/standalone/server.js');
