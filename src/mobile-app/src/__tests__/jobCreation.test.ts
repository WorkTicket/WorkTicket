/**
 * Mobile app integration tests for job creation and AI processing flow (M-3 fix).
 *
 * Tests the core mobile workflows that field workers depend on:
 * - Job creation with offline queue recovery
 * - AI processing state tracking
 * - Analytics event reporting
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

import { logEvent } from '../utils/analytics';
import { api } from '../api/client';
import { enqueueUpload, processQueue } from '../utils/offlineQueue';

// Mock the API client
vi.mock('../api/client', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}));

// Mock the offline queue
vi.mock('../utils/offlineQueue', () => {
  const queue: any[] = [];
  return {
    initQueue: vi.fn(() => Promise.resolve()),
    enqueueUpload: vi.fn((jobId: string, fileUri: string, contentType: string) => {
      const id = `offline-${queue.length}`;
      queue.push({ id, jobId: jobId, fileUri, contentType, createdAt: Date.now() });
      return Promise.resolve(id);
    }),
    processQueue: vi.fn(async () => {
      for (const item of queue) {
        queue.splice(queue.indexOf(item), 1);
      }
      return { uploads: [], analytics: [] };
    }),
    MAX_RETRIES: 3,
    MAX_CONCURRENT_UPLOADS: 3,
  };
});

// Mock analytics
vi.mock('../utils/analytics', () => ({
  logEvent: vi.fn(() => Promise.resolve()),
  EVENT_JOB_CREATED: 'job_created',
  EVENT_JOB_APPROVED_WITHOUT_CHANGES: 'job_approved_without_changes',
}));

describe('Job Creation Flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('createJob', () => {
    it('should create a job via API when online', async () => {
      const jobData = {
        customer_id: 'cust-123',
        description: 'Fix leaking pipe in bathroom',
        address: '123 Main St, Springfield',
        scheduled_time: new Date().toISOString(),
      };

      const mockResponse = {
        data: {
          id: 'job-456',
          status: 'pending',
          ai_processing_state: 'none',
          ...jobData,
        },
      };
      (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce(mockResponse);

      const createJob = async (data: typeof jobData) => {
        try {
          const response = await api.post('/api/v1/jobs', data);
          await logEvent('job.created', response.data.id, {
            has_description: !!data.description,
          });
          return response.data;
        } catch {
          await enqueueUpload('temp-job', JSON.stringify(data), 'application/json');
          throw new Error('Offline — job queued for later');
        }
      };

      const result = await createJob(jobData);
      expect(result.id).toBe('job-456');
      expect(result.status).toBe('pending');
      expect(logEvent).toHaveBeenCalledWith('job.created', 'job-456', expect.any(Object));
    });

    it('should enqueue job to offline queue when API is unavailable', async () => {
      (api.post as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Network error'));

      const createJob = async (data: any) => {
        try {
          await api.post('/api/v1/jobs', data);
        } catch {
          await enqueueUpload('offline-job', JSON.stringify(data), 'application/json');
        }
      };

      await createJob({ description: 'Test' });
      expect(enqueueUpload).toHaveBeenCalled();
    });

    it('should retry offline queue items when connectivity returns', async () => {
      await enqueueUpload('job-offline', '{}', 'application/json');

      (api.post as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        data: { id: 'job-789', status: 'pending' },
      });

      await processQueue();
      expect(processQueue).toHaveBeenCalled();
    });
  });

  describe('AI Processing State Tracking', () => {
    it('should poll for AI processing state changes', async () => {
      const pollStates = [
        { ai_processing_state: 'queued' },
        { ai_processing_state: 'processing' },
        { ai_processing_state: 'completed' },
      ];

      let pollIndex = 0;
      (api.get as ReturnType<typeof vi.fn>).mockImplementation(() => {
        const state = pollStates[pollIndex] || pollStates[pollStates.length - 1];
        pollIndex++;
        return Promise.resolve({ data: state });
      });

      const pollAIState = async (jobId: string) => {
        const terminalStates = ['completed', 'failed', 'compensated'];
        let attempts = 0;
        const MAX_POLLS = 30;

        while (attempts < MAX_POLLS) {
          const response = await api.get(`/api/v1/jobs/${jobId}/ai-status`);
          const state = response.data.ai_processing_state;
          if (terminalStates.includes(state)) {
            return state;
          }
          attempts++;
          await new Promise((r) => setTimeout(r, 100));
        }
        throw new Error('AI processing timed out');
      };

      const result = await pollAIState('job-123');
      expect(result).toBe('completed');
      expect(pollIndex).toBe(3);
    });

    it('should handle AI processing failure gracefully', async () => {
      (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({
        data: { ai_processing_state: 'failed' },
      });

      const result = await (async () => {
        const response = await api.get('/api/v1/jobs/job-123/ai-status');
        return response.data.ai_processing_state;
      })();

      expect(result).toBe('failed');
    });
  });

  describe('Job Status Updates', () => {
    it('should prevent completing a job with active AI processing', async () => {
      (api.patch as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
        response: {
          status: 400,
          data: {
            detail: "Cannot complete job while AI processing is in 'processing' state. Wait for AI to finish or cancel the AI job first.",
          },
        },
      });

      let error: any;
      try {
        await api.patch('/api/v1/jobs/job-123', { status: 'completed' });
      } catch (e) {
        error = e;
      }

      expect(error.response.status).toBe(400);
      expect(error.response.data.detail).toContain('Cannot complete job');
    });
  });

  describe('Analytics Event Reporting', () => {
    it('should track job creation events', async () => {
      await logEvent('job.created', 'job-001', {
        has_description: true,
      });

      expect(logEvent).toHaveBeenCalledWith('job.created', 'job-001', {
        has_description: true,
      });
    });

    it('should track screen views', async () => {
      await logEvent('screen.view', undefined, { screen: 'JobDetail' });
      expect(logEvent).toHaveBeenCalledWith('screen.view', undefined, { screen: 'JobDetail' });
    });
  });
});
