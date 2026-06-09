# ADR 003: Celery Queue Architecture

**Status:** Accepted
**Date:** 2026-06-05

## Context

WorkTicket uses Celery for background job processing, including AI analysis
of job descriptions, images, and audio. We needed to design a queue
architecture that prevents head-of-line blocking, isolates failures,
and supports graceful degradation.

## Decision

We implemented **4 dedicated Celery queues + beat queue** with per-queue
worker isolation:

| Queue | Purpose | Concurrency | Backpressure |
|-------|---------|-------------|-------------|
| `ai_text` | Text analysis (llama3.1) | 1 | 200 |
| `ai_audio` | Audio transcription (whisper) | 1 | 200 |
| `ai_image` | Image analysis (llama3.2-vision) | 1 | 200 |
| `default` | Background tasks, cleanup, billing | 1 | 500 |
| `beat` | Scheduled periodic tasks | 1 | N/A |

### Key Design Decisions:

1. **Separate queues per AI modality**: Prevents text processing from
   blocking image analysis and vice versa. Each modality has different
   latency and resource characteristics.

2. **Backpressure limits**: Per-queue task limits prevent unbounded
   queue growth. When a queue exceeds its limit, new tasks are rejected
   with a backpressure error (retried later).

3. **Prefetch=1**: Each worker fetches exactly 1 task at a time,
   eliminating head-of-line blocking within a queue.

4. **HMAC-signed task payloads**: All task payloads are HMAC-signed
   with the `CELERY_TASK_SIGNING_KEY`, preventing task forgery.

5. **Dual Beat HA**: Two beat schedulers with Redis lock acquisition
   ensure exactly one beat instance is active at any time.

## Consequences

### Positive
- No head-of-line blocking between AI modalities
- Independent scaling per queue type
- Clear failure isolation (AI text failure doesn't affect billing tasks)
- Predictable resource allocation per modality

### Negative
- **Static worker count**: Workers have fixed concurrency (c=1);
  no autoscaling for AI bursts. Mitigated by docker-compose replication
  and per-queue backpressure.
- **Operational complexity**: 5 queue types to monitor, each with
  separate worker lifecycle management.

### Dead Letter Queue (DLQ)
Failed tasks go to the DLQ after max retries. Poison detection (5 max
retries) prevents infinite retry loops. DLQ replay runs every 5 minutes
via beat task.
